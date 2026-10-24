// Browser side of passkey sign-up and sign-in (WebAuthn). The server verifies everything.
import { api } from "./api.js";

const toBytes = (s) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (s.length % 4)) % 4)), (c) => c.charCodeAt(0));
const toText = (buf) => (buf ? btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "") : null);

export const supported = () => Boolean(window.PublicKeyCredential && navigator.credentials);

function friendly(err) {
  if (err && err.name === "NotAllowedError") return new Error("The passkey prompt was closed or timed out. Try again.");
  if (err && err.name === "InvalidStateError") return new Error("This device already has a Kampan passkey. Use Sign in instead.");
  return err;
}

export async function signUp(name, invite) {
  const { challenge_id: challengeId, options } = await api("/api/auth/register/options", { name, invite });
  const publicKey = { ...options, challenge: toBytes(options.challenge), user: { ...options.user, id: toBytes(options.user.id) },
    excludeCredentials: (options.excludeCredentials || []).map((c) => ({ ...c, id: toBytes(c.id) })) };
  let cred;
  try { cred = await navigator.credentials.create({ publicKey }); } catch (err) { throw friendly(err); }
  const r = cred.response;
  const credential = { id: cred.id, rawId: toText(cred.rawId), type: cred.type,
    response: { clientDataJSON: toText(r.clientDataJSON), attestationObject: toText(r.attestationObject),
      transports: r.getTransports ? r.getTransports() : [] }, clientExtensionResults: cred.getClientExtensionResults() };
  return api("/api/auth/register/verify", { challenge_id: challengeId, credential, invite });
}

export async function signIn() {
  const { challenge_id: challengeId, options } = await api("/api/auth/login/options", {});
  const publicKey = { ...options, challenge: toBytes(options.challenge),
    allowCredentials: (options.allowCredentials || []).map((c) => ({ ...c, id: toBytes(c.id) })) };
  let cred;
  try { cred = await navigator.credentials.get({ publicKey }); } catch (err) { throw friendly(err); }
  const r = cred.response;
  const credential = { id: cred.id, rawId: toText(cred.rawId), type: cred.type,
    response: { clientDataJSON: toText(r.clientDataJSON), authenticatorData: toText(r.authenticatorData),
      signature: toText(r.signature), userHandle: toText(r.userHandle) }, clientExtensionResults: cred.getClientExtensionResults() };
  return api("/api/auth/login/verify", { challenge_id: challengeId, credential });
}
