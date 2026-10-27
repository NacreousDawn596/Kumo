import { useEffect, useRef, useState } from "react";
import { Mic, MicOff, Phone, PhoneOff } from "lucide-react";
import { acceptAnswer, addIce, answerCall, endCall, setMuted as setRemoteMuted, startCall } from "../lib/webrtc.js";
import { onEvent, sendEvent } from "../lib/realtime.js";
import "./call.css";

export default function CallBar({ conversationId, otherName }) {
  const room = `conversation:${conversationId}`;
  const [state, setState] = useState("idle"); // idle | calling | incoming | inCall
  const [muted, setMutedState] = useState(false);
  const pcRef = useRef(null);

  useEffect(() => {
    window.__kumoCallOnIce = (candidate) => sendEvent(room, { type: "call.ice", data: { candidate } });

    const off = onEvent((e) => {
      if (e.room !== room) return;
      if (e.type === "call.offer") {
        setState("incoming");
        window.__kumoPendingOffer = e.data.sdp;
      } else if (e.type === "call.answer") {
        acceptAnswer(e.data.sdp).then(() => setState("inCall"));
      } else if (e.type === "call.ice") {
        addIce(e.data.candidate);
      } else if (e.type === "call.hangup") {
        hangup();
      }
    });

    return () => {
      off();
      endCall();
    };
  }, [room]);

  const hangup = () => {
    sendEvent(room, { type: "call.hangup", data: {} });
    endCall();
    setState("idle");
  };

  const begin = async () => {
    try {
      const pc = await startCall((type, data) => sendEvent(room, { type, data }));
      pcRef.current = pc;
      setState("calling");
    } catch {
      setState("idle");
    }
  };

  const answer = async () => {
    try {
      await answerCall(window.__kumoPendingOffer, (type, data) => sendEvent(room, { type, data }));
      setState("inCall");
    } catch {
      setState("idle");
    }
  };

  const toggleMute = () => {
    setRemoteMuted(!muted);
    setMutedState((m) => !m);
  };

  if (state === "idle") {
    return (
      <button className="btn btn-ghost btn-sm" title="Start audio call" onClick={begin}>
        <Phone size={15} /> Call
      </button>
    );
  }

  if (state === "incoming") {
    return (
      <div className="call-bar call-incoming">
        <span>Incoming call from {otherName || "…"}</span>
        <button className="btn btn-primary btn-sm" onClick={answer}><Phone size={14} /> Accept</button>
        <button className="btn btn-danger btn-sm" onClick={hangup}><PhoneOff size={14} /> Decline</button>
      </div>
    );
  }

  return (
    <div className="call-bar">
      <span>{state === "calling" ? `Calling ${otherName || "…"}…` : "In call"}</span>
      <button className="btn btn-ghost btn-sm" onClick={toggleMute} title="Mute">
        {muted ? <MicOff size={15} /> : <Mic size={15} />}
      </button>
      <button className="btn btn-danger btn-sm" onClick={hangup}>
        <PhoneOff size={15} /> End
      </button>
    </div>
  );
}
