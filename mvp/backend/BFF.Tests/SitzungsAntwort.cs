using System.Net;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;
using Xunit;

namespace BFF.Tests;

/// <summary>
/// Liest die Antwort von /api/check-session und /api/user-info. Beide antworten immer mit 200,
/// ob jemand angemeldet ist, steht im Feld isAuthenticated: Besucher bekommen dort keine 401,
/// sonst sperrt fail2ban am Gateway eine geteilte IP (Saal-WLAN) nach 20 Seitenaufrufen.
/// </summary>
public static class SitzungsAntwort
{
    public static async Task<bool> AngemeldetAsync(HttpResponseMessage response)
    {
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        using var payload = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
        return payload.RootElement.GetProperty("isAuthenticated").GetBoolean();
    }
}
