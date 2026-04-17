# PLAN.md — ResumeX: Continuação e Evolução

> **Contexto de hardware:** RTX 4060 — 8GB VRAM  
> **Stack atual:** Flask + Groq Whisper (transcrição) + Groq / Gemini / Ollama (resumo) + UI web própria  
> **Objetivo:** Transformar o ResumeX em um sistema robusto de aprendizado a partir de áudio/vídeo, com valor de portfólio para a área de LLMs

---

## Estado atual do produto

O ResumeX já é uma aplicação web funcional e completa no fluxo base. O que existe hoje:

- **Transcrição:** upload de áudio/vídeo com processamento de áudio inteiramente no browser (Web Audio API → resample mono 16 kHz → WAV PCM → chunks de 24 MB → Groq Whisper)
- **Resumo multi-provider com streaming:** usuário escolhe entre Groq (Llama 3.3 70B), Gemini 2.5 Flash, Gemma2 9B via Ollama, ou Qwen3 8B via Ollama — todos com SSE/NDJSON em tempo real
- **UI web própria:** drag & drop, barra de progresso com log em tempo real, exibição de transcrição com contagem de palavras, renderização de Markdown (`marked.js`), exportação de PDF via `window.open()`
- **Tratamento de erros:** `RateLimitError` e `OllamaOfflineError` com feedback visual para o usuário
- **Deploy:** Dockerfile + docker-compose, Gunicorn com 2 workers

```
Entrada (áudio/vídeo)
        ↓
   Browser processa: resample → WAV → chunks
        ↓
   POST /transcrever → Groq Whisper
        ↓
   Transcrição exibida (+ word count)
        ↓
   Usuário seleciona provider
        ↓
   POST /resumir → LLM streaming (Groq / Gemini / Ollama)
        ↓
   Resumo em Markdown → exportação PDF
```

---

## Fase 0 — Consolidação da base atual

**Duração estimada:** 3–5 dias  
**Objetivo:** Fechar as lacunas de qualidade antes de construir em cima.

O que já está feito: `config.py`, `groq.py`, `summarizer.py`, blueprint Flask, tratamento de rate limit. O que falta:

### 0.1 Testes e logging

- Adicionar `pytest` com ao menos um fixture por caso crítico: transcrição curta, transcrição com áudio inválido, provider offline (mock do Ollama)
- Logging estruturado com `loguru` — essencial para debugar pipelines de LLM em produção
- Criar pasta `samples/` com 2–3 áudios de teste curtos para desenvolvimento offline (evitar gastar cota da API em dev)

### 0.2 Diarização de speakers

- Implementar identificação de speakers com `pyannote-audio` (roda local na RTX 4060)
- Saída: prefixar o texto transcrito com `[Speaker 1]:`, `[Speaker 2]:` etc.
- Melhora diretamente a qualidade do resumo em aulas, podcasts e reuniões
- Adicionar toggle na UI para ativar/desativar (aumenta o tempo de processamento)

### 0.3 Suporte explícito a vídeo no backend

Hoje o browser extrai o áudio localmente. Para arquivos grandes ou para a futura integração com URLs do YouTube, adicionar extração server-side:

```bash
ffmpeg -i video.mp4 -vn -ar 16000 -ac 1 audio.wav
```

**Entrega:** Codebase com testes básicos passando, logging em produção, diarização funcional.

---

## Fase 1 — RAG local sobre o conteúdo transcrito

**Duração estimada:** 2–3 semanas  
**Objetivo:** Usuário pode fazer perguntas sobre a aula/podcast que acabou de transcrever.

### 1.1 Chunking da transcrição

O texto transcrito é contínuo — precisa ser segmentado antes de indexar:

- **Chunking por tempo:** cada chunk carrega o timestamp (`[00:05:23]`) para referenciar o momento exato no áudio; Groq Whisper já retorna os timestamps, só falta usar
- **Chunking semântico:** `sentence-transformers` para detectar mudanças de tópico e criar chunks coerentes
- Tamanho alvo: 300–500 tokens, 50 tokens de sobreposição

```python
{
    "id": "chunk_007",
    "text": "...",
    "start_time": "00:05:23",
    "end_time": "00:07:41",
    "speaker": "Speaker 1",   # se diarização estiver ativa
    "embedding": [...]
}
```

### 1.2 Embeddings locais (RTX 4060)

`BAAI/bge-m3` roda confortavelmente nos 8GB de VRAM, multilíngue, sem custo de API:

```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("BAAI/bge-m3", device="cuda")
embeddings = model.encode(chunks, batch_size=32, show_progress_bar=True)
```

### 1.3 Vector store local com ChromaDB

- ChromaDB em modo persistente — sem servidor externo
- Cada conteúdo processado cria uma **collection separada** identificada por `doc_id`
- Metadados indexados: timestamp, speaker, índice do chunk

### 1.4 Endpoint `/ask`

- Recebe `doc_id` + pergunta do usuário
- Recupera os 3–5 chunks mais relevantes via similaridade
- LLM (Groq, já integrado) recebe contexto + pergunta e gera resposta com citação de timestamp
- Streaming da resposta via SSE (mesmo padrão já usado em `/resumir`)

**Entrega:** Campo de perguntas no painel de resumo → resposta com referência ao trecho do áudio.

---

## Fase 2 — Geração de material de estudo

**Duração estimada:** 2–3 semanas  
**Objetivo:** Transformar a transcrição em material ativo de aprendizado.

### 2.1 Flashcards automáticos

```python
FLASHCARD_PROMPT = """
A partir do trecho de aula abaixo, gere de 3 a 5 flashcards no formato:
FRENTE: [pergunta objetiva sobre o conceito]
VERSO: [resposta concisa e clara]

Trecho: {chunk}
"""
```

- Exportar no formato `.apkg` (Anki) com `genanki`
- Exportar também em CSV para outros apps de flashcard
- Botão "Gerar Flashcards" no painel de resultado, ao lado do "Gerar Resumo"

### 2.2 Quiz gerado por LLM

- Questões de múltipla escolha (4 alternativas) com 3 níveis de dificuldade
- Gabarito com justificativa e timestamp de referência
- Interface de quiz embutida na UI web existente (sem precisar de nova página)

### 2.3 Mapa de conceitos

- LLM extrai entidades e relações, retorna JSON:
  ```json
  {"nodes": ["X", "Y"], "edges": [{"from": "X", "to": "Y", "label": "causa"}]}
  ```
- Visualização com `pyvis` (HTML interativo) renderizada direto na UI

### 2.4 LLM local como opção adicional (RTX 4060)

Hoje Ollama já está integrado com Gemma2 e Qwen3. Para tarefas de geração de flashcards/quiz (que exigem JSON estruturado), considerar adicionar:

| Modelo | VRAM | Uso recomendado |
|---|---|---|
| `Qwen2.5-7B-Instruct` (Q4) | ~5.5GB | Geração de material estruturado |
| `Mistral-7B-Instruct-v0.3` (Q4) | ~5.5GB | Boa qualidade em português |

**Entrega:** Para cada conteúdo processado: resumo + flashcards `.apkg` + quiz interativo + mapa de conceitos.

---

## Fase 3 — Evolução da interface e suporte a YouTube

**Duração estimada:** 2–3 semanas  
**Objetivo:** A UI web já existe e funciona; evoluir sem reescrever do zero.

> **Nota:** a Fase 3 original planejava criar uma UI do zero com React. Como já temos uma UI funcional em HTML/CSS/JS vanilla, a prioridade é evoluir o que existe — só migrar para React se a complexidade dos novos componentes justificar.

### 3.1 Suporte a URLs do YouTube

- Campo de URL alternativo ao upload de arquivo
- `yt-dlp` baixa o áudio server-side e extrai título + thumbnail como metadados
- O resto do pipeline (transcrição, resumo, RAG) é igual

```python
import yt_dlp
def download_audio(url: str) -> dict:
    opts = {"format": "bestaudio/best", "postprocessors": [{"key": "FFmpegExtractAudio"}]}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    return {"title": info["title"], "duration": info["duration"]}
```

### 3.2 Biblioteca de documentos

- Persistir histórico de conteúdos processados (SQLite — simples, sem servidor)
- Grid na UI com todos os documentos salvos: título, data, duração, provider usado
- Reabrir qualquer documento e continuar fazendo perguntas via RAG

### 3.3 Migração da API para FastAPI (opcional)

Considerar migrar de Flask para FastAPI se:
- A complexidade dos endpoints crescer (especialmente com jobs assíncronos)
- Precisar de documentação OpenAPI automática para o portfólio

Se migrar, manter o mesmo padrão de SSE para streaming.

**Entrega:** App com suporte a YouTube, biblioteca de documentos, UX melhorada.

---

## Fase 4 — Agente MCP e automações

**Duração estimada:** 2–3 semanas  
**Objetivo:** Demonstrar expertise em MCP e agentes — o diferencial de portfólio mais forte.

### 4.1 Servidor MCP do ResumeX

Expor as capacidades do ResumeX como tools padronizadas via MCP SDK. Isso permite que o Claude Desktop (e outros clientes MCP) use o ResumeX como ferramenta.

```python
tools = [
    {"name": "transcribe_audio",    "input_schema": {"url_or_path": "string"}},
    {"name": "summarize_document",  "input_schema": {"doc_id": "string", "depth": "basic|detailed|comprehensive"}},
    {"name": "ask_document",        "input_schema": {"doc_id": "string", "question": "string"}},
    {"name": "generate_flashcards", "input_schema": {"doc_id": "string", "count": "integer"}},
]
```

### 4.2 Agente de estudo autônomo (LangGraph)

Dado um conjunto de documentos (ex.: todas as aulas de uma disciplina):
- Identificar lacunas de conteúdo entre as aulas
- Sugerir ordem de revisão baseada em dependências conceituais
- Gerar plano de estudos personalizado
- Responder perguntas usando múltiplos documentos como contexto RAG

### 4.3 Integração com Notion ou Obsidian

- Exportar resumos e flashcards para workspace do Notion (via API)
- Gerar vault do Obsidian com notas linkadas por conceito (`[[wikilink]]`)
- Cada aula vira uma nota; conceitos comuns criam links automáticos entre aulas

**Entrega:** Servidor MCP funcional demonstrável no Claude Desktop, agente de estudo com LangGraph, integração com pelo menos uma ferramenta de notas.

---

## Stack tecnológica

| Camada | Tecnologia | Estado |
|---|---|---|
| Transcrição | Groq Whisper API | ✅ implementado |
| LLM API | Groq (Llama 3.3) + Gemini 2.5 Flash | ✅ implementado |
| LLM local | Gemma2 9B + Qwen3 8B via Ollama | ✅ implementado |
| Streaming | SSE / NDJSON | ✅ implementado |
| UI web | HTML/CSS/JS vanilla, marked.js | ✅ implementado |
| Export PDF | window.open() + print | ✅ implementado |
| Deploy | Docker + Gunicorn | ✅ implementado |
| Testes | pytest | ❌ pendente |
| Logging | loguru | ❌ pendente |
| Diarização | pyannote-audio | ❌ pendente |
| Embeddings | BAAI/bge-m3 (local, CUDA) | ❌ fase 1 |
| Vector store | ChromaDB persistente | ❌ fase 1 |
| Flashcards | genanki (.apkg) | ❌ fase 2 |
| Suporte YouTube | yt-dlp | ❌ fase 3 |
| Histórico | SQLite | ❌ fase 3 |
| Servidor MCP | MCP Python SDK | ❌ fase 4 |
| Agente | LangGraph | ❌ fase 4 |

---

## Cronograma resumido

| Fase | Descrição | Duração |
|---|---|---|
| 0 | Testes, logging, diarização | 3–5 dias |
| 1 | RAG local com ChromaDB | 2–3 semanas |
| 2 | Flashcards, quiz, mapa de conceitos | 2–3 semanas |
| 3 | YouTube, biblioteca de documentos, UX | 2–3 semanas |
| 4 | Agente MCP + LangGraph | 2–3 semanas |
| **Total** | | **~9–13 semanas** |

---

## Próximo passo imediato

O fluxo base está funcional. Antes de qualquer nova feature, fechar a Fase 0:

1. Adicionar `pytest` + `loguru` ao `requirements.txt`
2. Criar `tests/test_transcription.py` com fixture de áudio curto em `samples/`
3. Substituir os `print()` espalhados pelo `loguru.logger`
4. Integrar `pyannote-audio` em `app/groq.py` como etapa pós-transcrição

Só depois partir para a Fase 1 (RAG + ChromaDB).

---

*Documento atualizado em 17/04/2026 — atualizar à medida que o projeto evoluir.*
