import { useCallback, useEffect, useRef, useState } from "react";

// Browser Web Speech API hook (STT + TTS)
export default function useSpeech() {
  const [supported, setSupported] = useState({ stt: false, tts: false });
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const recognitionRef = useRef(null);
  const onFinalRef = useRef(null);

  useEffect(() => {
    const SR =
      typeof window !== "undefined" &&
      (window.SpeechRecognition || window.webkitSpeechRecognition);
    const hasTTS = typeof window !== "undefined" && "speechSynthesis" in window;
    setSupported({ stt: !!SR, tts: hasTTS });
    if (!SR) return;
    const rec = new SR();
    rec.continuous = false;
    rec.interimResults = true;
    rec.lang = "en-US";
    rec.onresult = (ev) => {
      let interimText = "";
      let finalText = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const r = ev.results[i];
        if (r.isFinal) finalText += r[0].transcript;
        else interimText += r[0].transcript;
      }
      if (interimText) setInterim(interimText);
      if (finalText && onFinalRef.current) {
        setInterim("");
        onFinalRef.current(finalText.trim());
      }
    };
    rec.onend = () => {
      setListening(false);
      setInterim("");
    };
    rec.onerror = () => {
      setListening(false);
      setInterim("");
    };
    recognitionRef.current = rec;
    return () => {
      try {
        rec.stop();
      } catch {}
    };
  }, []);

  const startListening = useCallback((onFinal) => {
    onFinalRef.current = onFinal;
    try {
      recognitionRef.current?.start();
      setListening(true);
    } catch {}
  }, []);

  const stopListening = useCallback(() => {
    try {
      recognitionRef.current?.stop();
    } catch {}
    setListening(false);
  }, []);

  const speak = useCallback((text, { onStart, onEnd, voiceName } = {}) => {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utt = new SpeechSynthesisUtterance(text);
    utt.rate = 1.02;
    utt.pitch = 1.0;
    const voices = window.speechSynthesis.getVoices();
    if (voiceName) {
      const v = voices.find((x) => x.name === voiceName);
      if (v) utt.voice = v;
    } else {
      // Prefer a nicer English voice if available
      const preferred =
        voices.find((v) => /Google US English|Samantha|Jenny|Aria/i.test(v.name)) ||
        voices.find((v) => v.lang?.startsWith("en"));
      if (preferred) utt.voice = preferred;
    }
    utt.onstart = () => onStart && onStart();
    utt.onend = () => onEnd && onEnd();
    utt.onerror = () => onEnd && onEnd();
    window.speechSynthesis.speak(utt);
  }, []);

  const cancelSpeech = useCallback(() => {
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  }, []);

  return {
    supported,
    listening,
    interim,
    startListening,
    stopListening,
    speak,
    cancelSpeech,
  };
}
