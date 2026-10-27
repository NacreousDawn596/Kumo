// WebRTC 1:1 audio call over the existing WebSocket signaling channel.

let pc = null;
let localStream = null;
let remoteAudio = null;

function ensureRemoteAudio() {
  if (!remoteAudio) {
    remoteAudio = new Audio();
    remoteAudio.autoplay = true;
  }
  return remoteAudio;
}

function makePeerConnection() {
  const connection = new RTCPeerConnection({
    iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
  });
  connection.onicecandidate = (e) => {
    if (e.candidate) window.__kumoCallOnIce?.(e.candidate);
  };
  connection.ontrack = (e) => {
    ensureRemoteAudio().srcObject = e.streams[0];
  };
  return connection;
}

export async function startCall(sendSignal) {
  localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  pc = makePeerConnection();
  localStream.getTracks().forEach((t) => pc.addTrack(t, localStream));
  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  sendSignal("call.offer", { sdp: pc.localDescription });
  return pc;
}

export async function answerCall(offer, sendSignal) {
  localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  pc = makePeerConnection();
  localStream.getTracks().forEach((t) => pc.addTrack(t, localStream));
  await pc.setRemoteDescription(offer);
  const answer = await pc.createAnswer();
  await pc.setLocalDescription(answer);
  sendSignal("call.answer", { sdp: pc.localDescription });
  return pc;
}

export async function acceptAnswer(answer) {
  await pc.setRemoteDescription(answer);
}

export async function addIce(candidate) {
  if (pc) await pc.addIceCandidate(candidate);
}

export function endCall() {
  localStream?.getTracks().forEach((t) => t.stop());
  pc?.close();
  pc = null;
  localStream = null;
  if (remoteAudio) {
    remoteAudio.srcObject = null;
  }
}

export function setMuted(muted) {
  localStream?.getAudioTracks().forEach((t) => (t.enabled = !muted));
}
