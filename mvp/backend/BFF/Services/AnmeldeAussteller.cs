using System.Security.Claims;

namespace BFF.Services;

/// <summary>
/// Der Realm, dessen Anmeldungen das BFF annimmt: die konfigurierte Keycloak-Authority, so wie
/// Keycloak sie als Aussteller (<c>iss</c>) ins ID-Token schreibt.
///
/// Anlass: Beim Umzug in den eigenen Realm (#429) bekam jedes Mitglied eine neue Kennung. Ein
/// Anmelde-Cookie aus dem alten Realm lief aber gleitend weiter und schickte die alte Kennung
/// als X-User, Einwuerfe landeten unter ihr. KontoPruefung weist ein solches Cookie ab; ein
/// kuenftiger Realm-Wechsel braucht dafuer nur die neue Authority, keine Handarbeit.
///
/// Woher der Aussteller kommt: Einen Claim <c>iss</c> hat das Cookie nicht, der OIDC-Handler
/// uebernimmt ihn nicht ins Ticket (/api/user-info zeigt nur Kennung, Name, Mail). Aber jeder
/// Claim aus dem ID-Token traegt den Aussteller in <see cref="Claim.Issuer"/>, und das Cookie
/// speichert ihn mit. Gelesen wird er am Claim der Kennung -- genau der, der als X-User
/// weitergeht. Das gilt auch fuer Cookies, die vor dieser Pruefung ausgestellt wurden.
///
/// Registriert nur mit Keycloak; ohne (Direktanmeldung im Dev-Stack) gibt es keinen Aussteller.
/// </summary>
public sealed class AnmeldeAussteller
{
    public AnmeldeAussteller(string authority)
    {
        Issuer = Normalisiert(authority);
    }

    /// <summary>Die Authority ohne Schraegstrich am Ende, wie in Program.cs.</summary>
    public string Issuer { get; }

    /// <summary>Stammt die Kennung im Cookie aus dem konfigurierten Realm?</summary>
    public bool StammtVonHier(ClaimsPrincipal principal)
    {
        var aussteller = ClaimUtilities.GetUserIdClaim(principal)?.Issuer;
        return !string.IsNullOrWhiteSpace(aussteller)
            && string.Equals(Normalisiert(aussteller), Issuer, StringComparison.Ordinal);
    }

    private static string Normalisiert(string adresse) => adresse.Trim().TrimEnd('/');
}
