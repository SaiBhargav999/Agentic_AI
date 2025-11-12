import { useState, useRef, useEffect } from "react";
import {
  Button, TextField, Typography, Stack, Paper, CircularProgress, Divider,
} from "@mui/material";
import axios from "axios";

const CREW_API = "http://127.0.0.1:8000";
const AUTOGEN_WS = "ws://127.0.0.1:8001";

type Stage = "idle" | "clinician" | "pharmacist" | "done";

const stripMd = (s: string) =>
  s
    .replace(/\*{1,3}([^*]+)\*{1,3}/g, "$1")
    .replace(/^[-*+]\s+/gm, "")
    .replace(/`{1,3}[^`]*`{1,3}/g, "")
    .trim();

export default function App() {
  const [patientId, setPatientId] = useState("52664210");
  const [crewResult, setCrewResult] = useState<string | null>(null);
  const [loadingCrew, setLoadingCrew] = useState(false);

  const [stage, setStage] = useState<Stage>("idle");
  const [clinician, setClinician] = useState("");
  const [pharmacist, setPharmacist] = useState("");
  const [wsStatus, setWsStatus] = useState<"disconnected" | "connected">("disconnected");
  const [stageMessage, setStageMessage] = useState<string>("");

  const wsRef = useRef<WebSocket | null>(null);
  const autoScrollRef = useRef<HTMLPreElement | null>(null);

  // auto scroll
  useEffect(() => {
    if (autoScrollRef.current) {
      autoScrollRef.current.scrollTop = autoScrollRef.current.scrollHeight;
    }
  }, [clinician, pharmacist, stage]);

  // prefer simple readable status (Sonar: no nested ternary)
  useEffect(() => {
    if (stage === "done") setStageMessage("Complete.");
    else if (stage === "pharmacist") setStageMessage("Review in progress…");
    else setStageMessage("Summary in progress…");
  }, [stage]);

  const runCrew = async () => {
    setLoadingCrew(true);
    setCrewResult(null);
    try {
      const res = await axios.post(`${CREW_API}/assessment/comprehensive`, {
        patient_id: patientId,
      });
      const text = typeof res.data.summary === "string"
        ? res.data.summary
        : JSON.stringify(res.data, null, 2);
      setCrewResult(stripMd(text));
    } catch (err: any) {
      setCrewResult("Error: " + (err?.message ?? "unknown"));
    } finally {
      setLoadingCrew(false);
    }
  };

  const runAutogen = () => {
    setClinician(""); setPharmacist("");
    setStage("clinician");
    setWsStatus("disconnected");

    if (wsRef.current) wsRef.current.close();

    const ws = new WebSocket(`${AUTOGEN_WS}/ws/conversation/${patientId}`);
    wsRef.current = ws;

    ws.onopen = () => setWsStatus("connected");

    ws.onmessage = (e) => {
      const text: string = String(e.data);

      if (text.startsWith("[connected]")) return;

      if (text.trim() === "---") {
        setStage("pharmacist");
        return;
      }
      if (text.includes("Done.")) {
        setStage("done");
        return;
      }

      if (stage === "clinician" || stage === "idle") {
        setClinician((s) => (s + text));
      } else if (stage === "pharmacist") {
        setPharmacist((s) => (s + text));
      }
    };

    ws.onclose = () => setWsStatus("disconnected");
  };

  return (
    <Stack gap={3} p={4}>
      <Typography variant="h4">Healthcare Agent Dashboard</Typography>

      <Stack direction="row" gap={2} alignItems="center">
        <TextField
          label="Patient ID"
          value={patientId}
          onChange={(e) => setPatientId(e.target.value)}
          size="small"
        />
        <Button variant="contained" onClick={runCrew} disabled={loadingCrew}>
          {loadingCrew ? "Running..." : "RUN CREWAI ASSESSMENT"}
        </Button>
        <Button variant="outlined" onClick={runAutogen}>
          START AUTOGEN CONVERSATION
        </Button>
      </Stack>

      <Stack direction="row" gap={2}>
        <Paper style={{ flex: 1, padding: 16, minHeight: 380 }}>
          <Typography variant="h6">CrewAI Result</Typography>
          <Divider sx={{ my: 1 }} />
          {loadingCrew && <CircularProgress size={24} />}
          <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>{crewResult}</pre>
        </Paper>

        <Paper style={{ flex: 1, padding: 16, minHeight: 380 }}>
          <Stack direction="row" gap={1} alignItems="center">
            <Typography variant="h6">Autogen Stream</Typography>
            <Typography variant="body2" color="text.secondary">
              ({wsStatus})
            </Typography>
          </Stack>
          <Divider sx={{ my: 1 }} />

          <Typography variant="subtitle1" gutterBottom>
            Clinician
          </Typography>
          <pre
            ref={autoScrollRef}
            style={{
              whiteSpace: "pre-wrap",
              margin: 0,
              maxHeight: 160,
              overflow: "auto",
              background: "#fafafa",
              borderRadius: 8,
              padding: 8,
            }}
          >
            {stripMd(clinician)}
          </pre>

          <Divider sx={{ my: 1 }} />

          <Typography variant="subtitle1" gutterBottom>
            Pharmacist
          </Typography>
          <pre
            style={{
              whiteSpace: "pre-wrap",
              margin: 0,
              maxHeight: 140,
              overflow: "auto",
              background: "#fafafa",
              borderRadius: 8,
              padding: 8,
            }}
          >
            {stripMd(pharmacist)}
          </pre>

          <Typography variant="caption" color="text.secondary">
            {stageMessage}
          </Typography>
        </Paper>
      </Stack>
    </Stack>
  );
}
