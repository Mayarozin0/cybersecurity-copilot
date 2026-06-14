## Incident Summary

During the scheduled TCU firmware push, the API key was used from an unauthorized external IP to pull the package manifest shortly before rogue delivery began; a follow-up download attempt with the same key was blocked by MFA. The substituted CDN source failed the allowlist check, but enforcement was advisory-only so delivery proceeded. Affected vehicles ultimately stopped the install at signature verification, while a subset had already taken the legitimate update before the source switched.

---

**Date / Time:** 2024-11-14T02:58:41
**OEM:** Volkswagen · **Model:** ID.4 Pro Performance · **Year Range:** MY2023 · **Affected Vehicles:** 847

---

### Attack Profile

- **Type:** OTA Supply Chain / Tampered Firmware Delivery
- **Vector:** Leaked OTA distribution API key used from unauthorized external IP to pull package manifest, enabling substitution of CDN delivery source with rogue server
- **Entry Point:** OTA Distribution API (key OTA-API-KEY-7731) accessed via manifest endpoint from non-corporate IP
- **Target Systems:** OTA update distribution pipeline, ICAS1 TCU firmware update process
- **Affected Parts:** ICAS1 HW-03, MDM9628 TCU, OTA package manifest / CDN delivery channel

---

### Impact & Outcome

- **Safety Impact:** No vehicle control or safety-relevant systems were affected; tampered firmware was blocked by signature verification on all affected vehicles before installation.
- **Outcome:** All 847 vehicles that received the substituted package failed signature verification, aborted installation, and quarantined the file; 224 vehicles had already completed the legitimate update from the correct CDN before the substitution occurred. How the rogue CDN IP entered the manifest is unresolved and under VW ops forensic review.

---

### Indicators of Compromise

185.43.112.77 (rogue CDN IP, Frankfurt DE / AS47846 SEDO GmbH, domain parking), cdn-delivery-eu.vw-ota-services.net (domain registered 2024-11-12, TLS cert issued by Let's Encrypt R3 instead of expected DigiCert VW internal CA), 91.217.137.4 (Amsterdam NL / AS60781 LeaseWeb VPS, used with key OTA-API-KEY-7731 to retrieve manifest), Delivered package hash 7c2b491de830f1a4598bc02741ef983c12d09a7b554ef312ac78b309de12f041 (unregistered, status UNAUTHORIZED), Expected/registered hash a3f9c821b4e0d75f2c18e9a0341bdf92c7e541f0983abc12d4e67f190bc32a11


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Generated Search Query

Volkswagen ID.4 OTA supply chain attack using leaked distribution API key to substitute CDN firmware delivery, blocked by signature verification


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Mitigation Plan

## Immediate Containment
- Revoke and rotate the compromised OTA API key, then audit its access logs for further unauthorized use.
- Block the rogue IPs and impersonating domain at the firewall and DNS level.
- Preserve the quarantined package and manifest/access logs, and re-verify the subset that installed before substitution.

## Long-Term Hardening
- Convert CDN allowlist enforcement from advisory to blocking, mirroring the route hardening after the earlier BGP hijack (Case 1).
- Harden OTA API key management with scoped, short-lived credentials, IP allowlisting, and anomaly detection.
- Extend MFA to all sensitive OTA pipeline operations and keep signature verification a non-bypassable final gate.
