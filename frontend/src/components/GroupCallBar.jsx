import { useEffect, useRef, useState } from "react";
import { Mic, MicOff, Phone, PhoneOff, Users } from "lucide-react";
import { Room, RoomEvent, Track } from "livekit-client";

let roomInstance = null;

export default function GroupCallBar({ sessionId }) {
  const [joined, setJoined] = useState(roomInstance?.state === "connected");
  const [muted, setMuted] = useState(false);
  const [participants, setParticipants] = useState(1);
  const [error, setError] = useState("");
  const audioRefs = useRef([]);

  useEffect(() => {
    if (!roomInstance) return () => {};
    const onTrack = (track) => {
      if (track.kind === Track.Kind.Audio) {
        const el = track.attach();
        audioRefs.current.push(el);
      }
    };
    const onCount = () => setParticipants(1 + roomInstance.remoteParticipants.size);
    roomInstance.on(RoomEvent.TrackSubscribed, onTrack);
    roomInstance.on(RoomEvent.ParticipantConnected, onCount);
    roomInstance.on(RoomEvent.ParticipantDisconnected, onCount);
    roomInstance.on(RoomEvent.Disconnected, () => { setJoined(false); setParticipants(1); });
    return () => {
      roomInstance.off(RoomEvent.TrackSubscribed, onTrack);
      roomInstance.off(RoomEvent.ParticipantConnected, onCount);
      roomInstance.off(RoomEvent.ParticipantDisconnected, onCount);
    };
  }, [joined]);

  useEffect(() => () => roomInstance?.disconnect(), []);

  const join = async () => {
    setError("");
    try {
      const res = await fetch(`/api/calls/livekit-token?room=session-${encodeURIComponent(sessionId)}`, { credentials: "include" });
      if (!res.ok) { setError("Group calls unavailable — LiveKit is not configured."); return; }
      const { token, url } = await res.json();
      const room = new Room();
      await room.connect(url, token);
      await room.localParticipant.setMicrophoneEnabled(true);
      roomInstance = room;
      setJoined(true);
      setMuted(false);
      setParticipants(1 + room.remoteParticipants.size);
    } catch {
      setError("Could not join the group call.");
    }
  };

  const toggleMute = async () => {
    if (!roomInstance) return;
    await roomInstance.localParticipant.setMicrophoneEnabled(muted);
    setMuted((m) => !m);
  };

  const leave = async () => {
    await roomInstance?.disconnect();
    roomInstance = null;
    audioRefs.current.forEach((el) => el.remove());
    audioRefs.current = [];
    setJoined(false);
    setParticipants(1);
  };

  if (joined) {
    return (
      <div className="group-call-bar">
        <span className="group-call-live"><Users size={13} /> {participants}</span>
        <button className="call-btn" onClick={toggleMute} title={muted ? "Unmute" : "Mute"}>
          {muted ? <MicOff size={16} /> : <Mic size={16} />}
        </button>
        <button className="call-btn call-btn-end" onClick={leave} title="Leave call">
          <PhoneOff size={16} />
        </button>
      </div>
    );
  }

  return (
    <div className="group-call-bar">
      {error && <span className="group-call-error">{error}</span>}
      <button className="btn btn-secondary btn-sm" onClick={join} title="Join group call">
        <Phone size={14} /> Join group call
      </button>
    </div>
  );
}
