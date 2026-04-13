# Audio-Feature + Intent-Pipeline Design

**Datum:** 2026-04-13  
**Status:** Approved  
**Ziel:** Energie-Sprünge und Tempo-Chaos in generierten Playlists eliminieren; LLM-Halluzinationen durch Constraint-basierte Selektion verhindern.

---

## Problemstellung

Zwei Hauptprobleme mit der aktuellen Playlist-Generierung:

1. **Klanglich inkohärente Playlists** — Genre-Filter sind zu grob. Ein "Indie"-Pool enthält Tracks von 60 BPM bis 180 BPM, von Ambient bis Noise-Rock. Das LLM kann diese Dimension nicht filtern weil die Daten fehlen.
2. **LLM wählt Tracks direkt** — aus einem Pool von 500 Titeln. Dabei halluziniert es gelegentlich Tracks oder wählt bekannte Künstler über Nischen-Perlen. Fuzzy-Matching kompensiert das nachträglich, verliert aber Qualität.

---

## Lösung

Zwei neue Mechanismen, die kombiniert wirken:

- **Proposal 1 (Audio-Features):** Librosa extrahiert 5 akustische Merkmale pro Track einmalig im Hintergrund und speichert sie in SQLite.
- **Proposal 2 (Intent-Extraktion):** Das LLM gibt strukturierte akustische Constraints zurück statt direkt Tracks zu wählen. SQLite filtert damit einen klanglich vorqualifizierten Pool — bevor ALS und der Generierungs-LLM involviert werden.

---

## Architektur

### Daten-Flow (neu)

```
Nutzer-Prompt
  → Intent-LLM  →  { genres, decades, bpm_range, energy_max, acousticness_min }
  → SQLite-Query mit Audio-Constraints (OR IS NULL für noch nicht extrahierte Tracks)
  → ALS-Ranking (unverändert, aber Pool ist klanglich vorqualifiziert)
  → Generierungs-LLM (wählt Flow & Reihenfolge aus vorqualifiziertem Pool — deutlich reduziertes Halluzinations-Risiko)
  → Playlist + Narrativ
```

### Graceful Degradation

Tracks ohne extrahierte Features (`bpm IS NULL`) werden nie ausgeschlossen — Audio-Constraints greifen nur wenn die Daten vorhanden sind (`condition OR bpm IS NULL`). Das System funktioniert sofort nach dem Sync und verbessert sich schrittweise während die Hintergrund-Extraktion läuft.

---

## Komponenten

### 1. `backend/audio_features.py` (neu)

Hintergrund-Extraktion nach jedem Sync. Liest `file_path` aus SQLite, extrahiert via librosa, schreibt zurück.

**Extraktion pro Track (erste 60 Sekunden, ~0.8s/Track):**

| Feature | Librosa-Funktion | Bedeutung |
|---------|-----------------|-----------|
| `bpm` | `beat.beat_track()` | Tempo in BPM |
| `energy` | RMS (`sqrt(mean(y²))`) | Lautstärke/Intensität 0.0–1.0 |
| `spectral_centroid` | `feature.spectral_centroid()` | Klanghelligkeit in Hz |
| `zero_crossing_rate` | `feature.zero_crossing_rate()` | Perkussiv (hoch) vs. tonal (niedrig) |
| `acousticness` | HPSS-Ratio (harmonisch/gesamt) | Akustisch (1.0) vs. elektrisch (0.0) |

**Öffentliche API:**
- `extract_audio_features_background()` — startet als Daemon-Thread nach Sync
- Schreibt Fortschritt in `sync_state` (`audio_extraction_current`, `audio_extraction_total`)
- Unlesbare Dateien werden übersprungen und geloggt, stoppen die Extraktion nicht
- Neustart setzt fort wo aufgehört wurde (nur `bpm IS NULL`-Tracks)

### 2. DB-Schema-Änderungen (`backend/library_cache.py`)

**`tracks`-Tabelle — 6 neue Spalten via Migration:**
```sql
ALTER TABLE tracks ADD COLUMN bpm                REAL;
ALTER TABLE tracks ADD COLUMN energy             REAL;
ALTER TABLE tracks ADD COLUMN spectral_centroid  REAL;
ALTER TABLE tracks ADD COLUMN zero_crossing_rate REAL;
ALTER TABLE tracks ADD COLUMN acousticness       REAL;
ALTER TABLE tracks ADD COLUMN audio_extracted_at TEXT;
```

**`sync_state`-Tabelle — 2 neue Spalten:**
```sql
ALTER TABLE sync_state ADD COLUMN audio_extraction_current INTEGER DEFAULT 0;
ALTER TABLE sync_state ADD COLUMN audio_extraction_total   INTEGER DEFAULT 0;
```

**Neue Funktionen:**
- `get_tracks_without_audio_features()` — gibt Tracks mit `bpm IS NULL` zurück
- `save_audio_features(gerbera_id, features)` — schreibt extrahierte Werte
- `get_audio_extraction_state()` — liest Fortschritt für UI-Polling

**Geänderte Funktionen:**
- `get_tracks_by_filters(..., audio_constraints: AudioConstraints | None = None)` — wendet optionale Constraints an mit `OR bpm IS NULL`-Fallback
- `count_tracks_by_filters(..., audio_constraints: AudioConstraints | None = None)` — gleiche Constraints für korrekte Cost-Estimation im Filter-Preview

### 3. LLM Intent-Extraktion (`backend/analyzer.py`)

**Erweiterter System-Prompt** gibt dem LLM Mapping-Regeln mit:
- `bpm_min/bpm_max`: "langsam" → 40–80, "mittel" → 80–120, "treibend" → 120+
- `energy_max`: "ruhig" → 0.3, "entspannt" → 0.5; weglassen bei "energetisch"
- `acousticness_min`: "keine E-Gitarren/elektrisch" → 0.7, "akustisch" → 0.8

Constraints werden nur gesetzt wenn der Prompt klare akustische Hinweise enthält — bei neutralen Prompts bleibt `audio_constraints: null`.

**Erweitertes LLM-Output-Schema:**
```json
{
  "genres": ["Jazz", "Ambient"],
  "decades": ["1990s"],
  "reasoning": "...",
  "audio_constraints": {
    "bpm_min": 60,
    "bpm_max": 100,
    "energy_max": 0.4,
    "acousticness_min": 0.6
  }
}
```

### 4. Pydantic-Modelle (`backend/models.py`)

```python
class AudioConstraints(BaseModel):
    bpm_min: float | None = None
    bpm_max: float | None = None
    energy_max: float | None = None
    acousticness_min: float | None = None

class AnalyzePromptResponse(BaseModel):
    # ... bestehende Felder unverändert ...
    audio_constraints: AudioConstraints | None = None
```

### 5. Pipeline-Integration (`backend/generator.py`)

`generate_playlist_stream()` reicht `audio_constraints` aus der Analyse an `_get_tracks_from_cache()` durch. Kein weiterer Umbau — ALS-Ranking, Fuzzy-Matching, Narrative-Generierung bleiben unverändert.

### 6. API-Erweiterungen (`backend/main.py`)

**Neuer Endpoint:** `GET /api/library/audio-status`
```json
{
  "total": 50000,
  "extracted": 12340,
  "is_extracting": true
}
```

**Sync-Endpoint** (`POST /api/library/sync`) triggert nach dem Sync den Audio-Extraktion-Thread.

### 7. Docker-Konfiguration (`docker-compose.yml`)

```yaml
volumes:
  - /pfad/zur/musik:/pfad/zur/musik:ro
```

Container-Pfad = Host-Pfad, damit die in Gerbera gespeicherten `file_path`-Werte direkt verwendbar sind. Kein Pfad-Remapping nötig.

### 8. Dependencies (`requirements.txt`)

```
librosa>=0.10.0
numpy>=1.24.0   # bereits transitiv vorhanden, explizit pinnen
```

---

## Geänderte Dateien

| Datei | Art | Beschreibung |
|-------|-----|-------------|
| `backend/audio_features.py` | Neu | Librosa-Extraktion, Hintergrund-Thread |
| `backend/library_cache.py` | Geändert | Schema-Migration, 3 neue Funktionen, erweitertes `get_tracks_by_filters` |
| `backend/analyzer.py` | Geändert | Erweiterter System-Prompt, Audio-Constraints aus LLM-Response parsen |
| `backend/models.py` | Geändert | `AudioConstraints`-Modell, `AnalyzePromptResponse` erweitert |
| `backend/generator.py` | Geändert | `audio_constraints` durchreichen |
| `backend/main.py` | Geändert | Extraktion nach Sync triggern, neuer Status-Endpoint |
| `docker-compose.yml` | Geändert | Read-only Music-Volume hinzufügen |
| `requirements.txt` | Geändert | `librosa` hinzufügen |

---

## Nicht im Scope

- Frontend-Anzeige der Audio-Constraints im UI (separate Feature-Arbeit)
- MFCC-Embeddings / "klingt wie dieser Track"-Similarity (Proposal C, zu aufwändig)
- Seed-Track Audio-Ähnlichkeit (separate Erweiterung)
- Stimmungs-Extraktion via ML-Modell (valence, nicht extrahierbar ohne externes Modell)

---

## Risiken

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|-------------------|------------|
| Librosa kann Dateiformat nicht lesen (z.B. altes MP3, FLAC-Variante) | Mittel | Try/except pro Track, überspringen + loggen |
| Audio-Extraktion blockiert Sync-Fortschritt im UI | — | Separater State-Slot in `sync_state`, unabhängiges Polling |
| LLM setzt Constraints zu aggressiv → leerer Pool | Niedrig | `OR bpm IS NULL` stellt sicher dass nicht-extrahierte Tracks immer enthalten sind; wenn extrahierte Tracks < 50 nach Constraints: Audio-Constraints vollständig ignorieren (nur Genre/Decade-Filter) |
| Docker-Volume-Pfad weicht von Gerbera-Pfad ab | Niedrig | Dokumentation, Config-Option für Pfad-Prefix |
