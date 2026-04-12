# CPU-Optimized Model Strategy for i5-1035G7 (4 cores)

## Recommended Model Stack

### Tier 1: Ultra-Light (TinyLlama 1.1B)
- **Model:** `tinyllama:latest`
- **Download Size:** ~650MB
- **Memory Usage:** ~1.2GB when loaded
- **Inference Speed:** <500ms for simple queries
- **Best For:** Greetings, time/date, simple factual lookups
- **Cost:** Minimal CPU impact, can run on single core
- **Install:** `ollama pull tinyllama`

### Tier 2: Fast (Phi-3 Mini 3.8B or Mistral 7B Q4)
- **Model:** `phi3:latest` (recommended) or `mistral:7b`
- **Download Size:** 2.3GB (Phi-3) or 3.8GB (Mistral)
- **Memory Usage:** 4GB (Phi-3) or 6GB (Mistral)
- **Inference Speed:** 1-3s for most queries
- **Best For:** General Q&A, summarization, moderate reasoning
- **Cost:** Balanced—uses 2-3 cores, acceptable latency
- **Install:** `ollama pull phi3` (or `ollama pull mistral:7b`)

### Tier 3: Capable (Mistral 7B or Llama3:8b)
- **Model:** `mistral:7b` (already configured) or `llama3:8b` (fallback)
- **Download Size:** 3.8GB
- **Memory Usage:** 6GB when loaded
- **Inference Speed:** 3-10s for complex tasks
- **Best For:** Code generation, reasoning, multi-step analysis
- **Cost:** Higher latency, uses all 4 cores, necessary for quality
- **Install:** `ollama pull mistral:7b`

## Loading Strategy (Minimize Switching Cost)

**Recommended:** Keep 2-3 models available on disk; load 1-2 by default.

### Option A: Speed-Optimized (Default)
```bash
# Keep Mistral as default (general purpose)
# Load Phi-3 Mini only when needed
ollama pull tinyllama
ollama pull phi3
ollama pull mistral:7b
```
- **Overhead:** ~6.7GB total disk space
- **Typical Memory:** 6GB (Mistral loaded) + swap for Phi-3 when needed
- **Switching Cost:** 5-10s when switching models

### Option B: Conservative (Limited Disk)
```bash
# Only keep Mistral available
# Skip TinyLlama for now, add later if needed
ollama pull mistral:7b
```
- **Overhead:** 3.8GB disk space
- **Typical Memory:** 6GB
- **Switching Cost:** N/A (single model)
- **Trade-off:** Slower for trivial queries, but simplest setup

## Router Configuration

The router now uses 3-tier complexity matching:

1. **Ultra-trivial queries** → TinyLlama (`llm_ultra_light`)
   - Patterns: `"hi"`, `"hello"`, `"what time"`, etc.
   - Response: <500ms

2. **Simple factual queries** → Phi-3 Mini (`llm_phi_fast`)
   - Patterns: `"what is"`, `"who is"`, `"explain briefly"`, etc.
   - Response: 1-3s

3. **Complex reasoning** → Mistral 7B (`llm_capable`)
   - Patterns: `"explain"`, `"why"`, `"code"`, etc.
   - Response: 3-10s

## Performance Expectations on i5-1035G7

| Query Type | Model | Response Time | CPU Util |
|-----------|-------|---|---|
| `"what time is it"` | TinyLlama | 400-600ms | 1-2 cores |
| `"what is machine learning"` | Phi-3 | 1.5-3s | 3-4 cores |
| `"write a python function to sort a list"` | Mistral | 5-10s | 4 cores maxed |

## Installation Steps

```bash
# 1. Pull the models
ollama pull tinyllama
ollama pull phi3
ollama pull mistral:7b

# 2. Verify they're loaded
curl -sS http://192.168.75.95:11434/api/tags | jq '.models[].name'

# 3. Restart orchestrator to load new agent configs
# (On LXC host)
systemctl restart llm-orchestrator
# or manual restart of your Python venv
```

## Disk Space Requirements

- **TinyLlama:** 650MB
- **Phi-3 Mini:** 2.3GB
- **Mistral 7B:** 3.8GB
- **Total (all 3):** ~6.7GB
- **Type:** Should use SSD if available for faster model loading

## Memory Planning

- **Base OS:** ~200-500MB
- **Ollama daemon:** ~100-200MB
- **Loaded model:** 1.2GB (Tiny) - 6GB (Mistral)
- **Python orchestrator:** ~100-200MB
- **Home Assistant (if on same host):** ~300-500MB
- **Total available:** Recommend 8GB+ RAM for comfortable headroom

## Monitoring & Tuning

If performance is poor:
1. Check CPU temp: `cat /sys/class/thermal/thermal_zone0/temp`
2. Monitor memory: `free -h`
3. Check if swap is being used: `vmstat 1 5`
4. Consider disabling TinyLlama tier if memory-constrained
5. Lower quantization of Mistral (use Q3 if available) for ~30% speed improvement

## Cost-Benefit Analysis

| Decision | Cost | Benefit |
|----------|------|---------|
| Add TinyLlama | 650MB disk, 5s load time | <500ms responses for trivial queries |
| Add Phi-3 Mini | 2.3GB disk, 5-10s load time | 1-3s responses, better than Mistral for most queries |
| Keep only Mistral | Simplest, lowest overhead | No optimization for trivial queries |
| Upgrade to "capable" model | Higher response time | Only marginal quality improvement for CPU constraints |

**Recommendation:** Start with **Option A** (all 3 models). The speed improvements for typical queries (greeting, time check) are worth the ~6.7GB disk space and occasional 5-10s switching cost.
