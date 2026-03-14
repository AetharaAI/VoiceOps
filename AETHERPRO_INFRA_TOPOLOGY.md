### AetherPro Technologies Infrastructure Topology

** Company Domains

** AetherPro.us - Main Corporate Landing Page
* subdomains:	operations.aetherpro.us - AetherOps
		tts.aetherpro.us - Chatterbox-TTS-Server
		embed.aetherpro.us - Embedding & Reranker endpoints
		asr.aetherpro.us - Aether-ASR-Sever
		perception.aetherpro.us - L4-360 vllm, transformers - llm inference endpoints
		audio.aetherpro.us - AI Acoustic Perception Engine
		
** AetherPro.tech - AetherOS Chat Interface
* subdomains:   api.aetherpro.tech - L40S-90 vllm/litellm llm inference endpoints
		triad.aetherpro.tech - R3-64 Triad Intelligence Memory & Databases
		
		These 2 Domains are the newest & need attention
* **SyndicateAI.co - Syndicate Marketplace for Agents, Humans & Businesses to find each - The Future of Work
** Redwatch.us - Redwatch - Autonomous Security & Compliance for Modern Defense Contractors
		
** BlackboxAudio.tech - AI Powered Audio Acoustic's Workbench
* subdomains:   api.blackboxaudio.tech - L40S-180 vllm/litellm llm inference endpoints
		asr.blackboxaudio.tech - Sub domain exists in DNS records for L4-360
		
** Perceptor.us - Sensor Fusion OCR & Vision Perception System(DoD)
* subdomains:   fabric.perceptor.us


** PassportAlliance.org - Passport Alliance Federation - APIS Agent Passport Identity Service
* subdomains:   docs.passportalliance.org

** PassportAlliance.us - URL Redirect to Passportallaince.org
* submains:     <to be determined>

** MCPFabric.space - Agentic MCP Tool Server * A2A Comms - Observersation & Registry
* subdoamins:   

** aetheragentforge.org → Agent Marketplace frontend
* subdomains:   api.aetheragentforge.org → Backend for marketplace currently on B3-16


* DOI: https://doi.org/10.5281/zenodo.18820877
* Gibson, C. M. (2026). Passport Alliance Specification (APIS v1.0): Agent Passport™ Issuance Standard (1.0). AetherPro Technologies LLC. https://doi.org/10.5281/zenodo.18820877

# AetherPro Tailscale Mesh — Canonical Node & Workload Map

## 1. **L40S-180 — Dual-GPU Primary Inference Node**

**Role:** Core LLM inference (sharded)

* **GPUs:** 2× L40S
* **Workloads:**

  * **Qwen3.5-122B-A10-AWQ-4bit** - Primary & Current running model
  
  * These model exist in the 1TB block storage attached to this node
  * Note: 1TB Block is divided into 3 partions
  
  * **Qwen3-80B-Next-Instruct-AWQ-4bit** - /mnt/aetherpro-extra1/models/
  * **Kimi-30B-Linear - /mnt/aetherpro-extra1/models/
  * **Kimi-K2.5 - Full model /mnt/aetherpro-extra2/models/ - Only model in this partition
  * 
  
  * Possible Future Downloads
  * **cyankiwi/MiniMax-M2.5-AWQ-4bit** - 37B Quant
  * **

  * LiteLLM base_url-https://api.blackboxaudio.tech/v1
  * LiteLLM dev api_key=sk-aether-master-pro
  * LiteLLM model_name=qwen3-next-instruct
# New model to test replacing text only Next model
  * LiteLLM model_name=qwen3.5-122 - Currently running as 03-01-2026 - AetherOps Runtime Harness

    * Sharded across both GPUs
    * Primary “main brain” model
* **Notes:**

  * High-value intelligence node
  * Do not disturb without intent
  * Treated as a single logical inference unit
  
  * Possibly considering quantizized Minimax-M2.5
---

## 2. **L40S-90 — Vision + Multimodal Node**

**Role:** Vision / multimodal inference

* **GPUs:** 1× L40S
* **Workloads:**


  * **Qwen3.5-35B-A3-AWQ-4bit** - Current Running Model - 03-05-2026
  
  * These are all in the 500GB Block Attached to this node.
  * **Qwen3.5-9B-AWQ-INT8** 
  * **Qwen3.5-4B-AWQ-4bit**
  * **Jan-Code-4B-AWQ-4bit**
  * **Nanbeige4 (NANBEIGE4-3B-THINKING)**- Long Horizon Agentic Model
  * **MiniCPM-V 4.5** - Excellent Small Vision Model
  * **Qwen3-VL-30B-Instruct-AWQ-8bit - Legacy Primary
  * **Stepfun-10B
  
  
  * LiteLLM_2 base_url=https://api.aetherpro.tech/v1
  * LiteLLM_2 dev api_key=sk-aether-sovereign-master-key-2026
  * LiteLLM_2 model_name=nanbeige4-3b-thinking
  * LiteLLM_2 model_name=minicpm-v
  
    * Secondary high-value intelligence node
* **Notes:**

  * Dedicated to multimodal workloads
  * Stable, intentionally colocated models

---

## 3. **L4-360 — Multi-GPU Services Node**

**Role:** Embeddings, TTS, experimental ASR / security models

* **GPUs:** 4× NVIDIA L4 (GPU0–GPU3)

### GPU Allocation

* **GPU0**

  * **BGE Embeddings**
  * https://embed.aetherpro.us/v1/embeddings
  * **BGE Re-ranker**
  * https://embed.aetherpro.us/rerank
* **GPU1**

  * **cyankiwi/VulnLLM-R-7B-AWQ-8bit - Redwatch.us Cyber Security Finetune - Needs Attention
  * **Qwen3-VL-8B-Herotic     - Special Uncensored Finetune for Redwatch - Spun Down for Vuln launch
  
  * Future Downloads
  * **kangali/durs-llm-web-scanner - fine-tuned to classify cybersecurity-related inputs.
  * Several more notes on security modecards in Redwatch-Mini
  * Currently free
* **GPU2**

  * **Aether-ASR-Server** (with UI)- Miror Image of Chatterbox-TTS-Server for ASR
  * **Systran/Whisper-v3** - Batch ASR for accuracy
  * **Kokoro-82M** - Realtime ASR for realtime low latency tasks
* **GPU3**

  * **Chatterbox TTS Server** (with UI)
  * https://tts.aetherpro.us - Chattbox-TTS-Server UI
  * https://tts.aetherpro.us/docs - Swagger API Docs
### In-Progress / Attempted

* **VulnLLM-R 7B (AWQ 8-bit)**

  * Allocation issues encountered
  * Core problem: incorrect GPU binding / launch command
* **Notes:**

  * This node is your **service multiplexor**
  * Needs intelligent GPU-aware scheduling
  * Prime candidate for automated deployment control


###  NEW CPU VM PROVISIONED ON 03-05-2026 - 
##      **C3-32 (US-West-OR-1) - AetherGateway/Platform - Aether VoiceOps - Voice Agents**

  * Specifically provisioned to host AetherPro's Primary Gateway & Control Plane
  * Currently Running VoiceOps - GohighLevel Voice Agent Competitor
  ** The SyndicateAI MArket is in development but need attention ASAP this is the future of work
  Purchased syndicateai.co on 3-04-2026 on Namecheap Monorepo MVP ready for deployment
  * SyndicateAI Agents/Humans/Businesses Marketplace - Where Autonomous Agents Meet find work
---

## 4. **B3-16 (US-East-VA-1) — Application Backend Node**

**Role:** SaaS backends

* **Workloads:**

  * **Aether Agent Forge**

    * https://aetheragentforge.org
    * Backend for AI Agent Marketplace
  * **Aether Ops**

    * https://operations.aetherpro.us
* **Notes:**

  * Business-critical
  * Mostly CPU / API / orchestration workloads

---

## 5. **B3-32 Flex (US-East-VA-1) — Identity & MCP Node**

**Role:** Identity, auth, protocol services

* **Workloads:**

  * **Passport**

    * https://passport.aetherpro.us
    * Passport - Keycloak-fork 
  * **MCP Fabric**

    * https://mcpfabric.space
    * Agentic MCP Server & A2A Comms
* **Notes:**

  * Long-lived infra
  * Rarely touched, high trust surface

---

## 6. **Triad Node — R3-64 (US-West-OR-1)**

**Role:** Data spine / intelligence backbone

* **Datastores:**

  * **PostgreSQL ×2**
  * **Redis Stack ×2**
  * **MongoDB ×2**
  * **Qdrant ×1**
  * **Weaviate ×1**
* **Purpose:**

  * Memory
  * State
  * Vector search
  * Coordination
* **Notes:**

  * This is the **Triad Spine**
  * Absolutely not a playground
  * Everything depends on this node

---

## 7. **User Devices**

* **CJ Laptop(s)**

  * Dev
  * Orchestration
  * Manual intervention
* **Role:**

  * Human control plane
  * Not part of automated deployment pool

---

# Qdrant (Vector Store)
QDRANT_URL=http://100.87.16.38:6333
QDRANT_HOST=100.87.16.38
QDRANT_PORT=6333
QDRANT_GRPC_PORT=6334
QDRANT_API_KEY=
QDRANT_GRPC_ENABLED=true

# Embedding Model (bge-m3 via TEI on L4 cluster)
EMBEDDING_API_URL=https://embed.aetherpro.us/v1/embeddings
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIMS=1024

# Reranker (bge-reranker-v2-m3 via TEI on L4 cluster)
RERANKER_API_URL=https://embed.aetherpro.us/rerank

# --- Postgres ---
DATABASE_URL=postgresql://redwatch_ops:redwatch_ops_gmccmg_2026_infra@100.87.16.38:5440/operations
DB_NAMES=redwatch, operations, litellm
DB_POOL_MIN=2
DB_POOL_MAX=20

# --- Redis --
REDIS_PASSWORD=redwatch_ops_gmccmg_2026_infra
REDIS_HOST_PORT=6380
REDIS_URL=redis://:redwatch_ops_gmccmg_2026_infra@100.87.16.38:6380

# --- Mongo ---
* Agent Harness - Mongo - Curently using MinimaxM2.5
AETHER_MONGO_URI=mongodb://aether_agent:aether_admin_max_agent_2026_operations@100.87.16.38:27018/aether_memory?authSource=aether_memory
* AetherOps Mongo Connection Info - Currently uses Qwen3-Next-Instruct or Qwen3.5-122B
MONGO_URL=mongodb://aether_admin:aetherops_mongo_agent_ledger_2026@100.87.16.38:27017/?authSource=admin
MONGO_DB_NAME=aether_agent
MONGO_LEDGER_DB_NAME=agent_ledger
# Context window — must match --max-model-len in your vLLM serve command
MAX_CONTEXT_TOKENS=262144

#### This is what my agent harness use to connect to mongo:
        print("[Memory] Connecting to MongoDB...")
        mongo_uri = os.getenv("AETHER_MONGO_URI", "mongodb://aether_agent:aether_admin_max_agent_2026_operations@100.87.16.38:27018/aether_memory?authSource=aether_memory")
        self.mongo = AsyncIOMotorClient(mongo_uri)
        await self.mongo.admin.command('ping')
        print("[Memory] MongoDB connected")
