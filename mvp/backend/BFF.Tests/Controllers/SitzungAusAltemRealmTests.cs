using Xunit;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using System;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Net.Http.Json;
using System.Threading.Tasks;
using BFF.Logging;
using BFF.Tests.Logging;

namespace BFF.Tests.Controllers;

/// <summary>
/// Nach einem Realm-Wechsel (#429: vom Realm der Netzbegruenung in den eigenen) weist das BFF
/// Anmelde-Cookies aus dem alten Realm ab. Sie liefen sonst 14 Tage gleitend weiter und
/// schickten die alte Kennung als X-User; Einwuerfe landeten unter ihr, und die Person sah
/// ihre eigenen Beitraege nicht.
///
/// Das Cookie kommt aus der echten Anmeldung gegen die Keycloak-Attrappe
/// (KeycloakLoginCookieTests, Aussteller <see cref="KeycloakLoginCookieTests.Authority"/>).
/// Der zweite Host hat denselben Schluesselring, aber eine andere Authority: so wie das BFF nach
/// dem Umstellen von Keycloak:Authority.
/// </summary>
public class SitzungAusAltemRealmTests : IDisposable
{
    private const string NeuerRealm = "https://keycloak.invalid/realms/neu";
    private const string SchreibendeRoute = "/api/v1/rawinput/";
    private const string Email = "beta@example.org";

    private readonly string _verzeichnis =
        Path.Combine(Path.GetTempPath(), $"gutgesagt-realmwechsel-{Guid.NewGuid():N}");
    private string NutzerDatei => Path.Combine(_verzeichnis, "managed-users.json");

    public SitzungAusAltemRealmTests()
    {
        Directory.CreateDirectory(_verzeichnis);
        BetaZugangsliste.SchreibenNach(
            NutzerDatei, BetaZugangsliste.Zugang(Email, "beta-001", displayName: "Beta Person"));
    }

    public void Dispose() => Directory.Delete(_verzeichnis, recursive: true);

    private WebApplicationFactory<Program> CreateHost(string authority, ILoggerProvider? logs = null) =>
        new WebApplicationFactory<Program>().WithWebHostBuilder(builder =>
        {
            builder.UseContentRoot(AppContext.BaseDirectory);
            builder.UseEnvironment("Development");
            builder.UseSetting("USE_KEYCLOAK", "true");
            builder.UseSetting("FRONTEND_URL", "http://localhost:4200");
            builder.UseSetting("BACKEND_URL", "http://127.0.0.1:1");
            builder.UseSetting("Keycloak:Authority", authority);
            builder.UseSetting("Keycloak:ClientId", KeycloakLoginCookieTests.ClientId);
            builder.UseSetting("Keycloak:ClientSecret", "test-secret");
            builder.UseSetting("MANAGED_USERS_PATH", NutzerDatei);
            builder.UseSetting("GELOESCHTE_KONTEN_PATH", Path.Combine(_verzeichnis, "geloeschte-konten.txt"));
            builder.UseSetting("DATAPROTECTION_KEYS_PATH", KeycloakLoginCookieTests.SchluesselringPfad);
            if (logs is not null)
            {
                builder.ConfigureServices(services => services.AddSingleton(logs));
            }
        });

    private static HttpClient Client(WebApplicationFactory<Program> factory) =>
        factory.CreateClient(new WebApplicationFactoryClientOptions
        {
            AllowAutoRedirect = false,
            HandleCookies = false
        });

    private static async Task<string> KeycloakCookieAsync()
    {
        using var response = await KeycloakLoginCookieTests.LoginAsync(returnUrl: null);
        var cookie = KeycloakLoginCookieTests.AuthCookie(response);
        return $"{cookie.Name}={cookie.Value}";
    }

    private async Task<HttpResponseMessage> SendeAsync(
        string authority, string cookie, HttpRequestMessage request, ILoggerProvider? logs = null)
    {
        using var factory = CreateHost(authority, logs);
        using var client = Client(factory);
        using (request)
        {
            request.Headers.Add("Cookie", cookie);
            return await client.SendAsync(request);
        }
    }

    private Task<HttpResponseMessage> CheckSessionAsync(string authority, string cookie, ILoggerProvider? logs = null) =>
        SendeAsync(authority, cookie, new HttpRequestMessage(HttpMethod.Get, "/api/check-session"), logs);

    [Theory]
    [InlineData(KeycloakLoginCookieTests.Authority)]
    [InlineData(KeycloakLoginCookieTests.Authority + "/")]
    public async Task CookieVomKonfiguriertenRealm_GiltWeiter(string authority)
    {
        var cookie = await KeycloakCookieAsync();

        using var response = await CheckSessionAsync(authority, cookie);

        Assert.True(await SitzungsAntwort.AngemeldetAsync(response));
    }

    [Fact]
    public async Task CookieAusAltemRealm_Abgewiesen_UndImBrowserGeloescht()
    {
        var cookie = await KeycloakCookieAsync();

        using var response = await CheckSessionAsync(NeuerRealm, cookie);

        Assert.False(await SitzungsAntwort.AngemeldetAsync(response));
        var geloescht = KeycloakLoginCookieTests.AuthCookie(response);
        Assert.True(geloescht.Expires < DateTimeOffset.UtcNow, "the auth cookie is not expired");
    }

    [Fact]
    public async Task CookieAusAltemRealm_SchreibendeRouteAbgewiesen()
    {
        var cookie = await KeycloakCookieAsync();

        using var response = await SendeAsync(NeuerRealm, cookie, new HttpRequestMessage(HttpMethod.Post, SchreibendeRoute)
        {
            Content = JsonContent.Create(new { content = "unter der alten Kennung" })
        });

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task CookieAusAltemRealm_LogZeileNurMitPseudonym()
    {
        var cookie = await KeycloakCookieAsync();
        var logs = new CapturingLoggerProvider();

        using var response = await CheckSessionAsync(NeuerRealm, cookie, logs);

        var text = logs.TextAtOrAbove(LogLevel.Information);
        Assert.Contains("another realm", text);
        Assert.Contains(LogPseudonym.Of(KeycloakLoginCookieTests.Kennung), text);
        Assert.DoesNotContain(KeycloakLoginCookieTests.Kennung, text);
    }

    /// <summary>Beta-Zugaenge haben keinen Aussteller; fuer sie bleibt es bei managed-users.json.</summary>
    [Fact]
    public async Task BetaZugang_NachRealmWechsel_GiltWeiter()
    {
        string cookie;
        using (var factory = CreateHost(KeycloakLoginCookieTests.Authority))
        using (var client = Client(factory))
        using (var login = await client.PostAsJsonAsync(
                   "/api/auth/login/managed", new { email = Email, password = BetaZugangsliste.Passwort }))
        {
            Assert.Equal(HttpStatusCode.OK, login.StatusCode);
            var c = KeycloakLoginCookieTests.AuthCookie(login);
            cookie = $"{c.Name}={c.Value}";
        }

        using var response = await CheckSessionAsync(NeuerRealm, cookie);

        Assert.True(await SitzungsAntwort.AngemeldetAsync(response));
    }
}
