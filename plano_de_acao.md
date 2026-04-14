# Plano de Ação — Integração ResumeX × WhatsApp

## Visão geral

Permitir que usuários enviem um vídeo ou áudio pelo WhatsApp, iniciem uma conversa guiada com o bot ResumeX e recebam a transcrição e/ou resumo de volta — em texto ou como PDF — diretamente na conversa.

---

## Serviço escolhido: Meta WhatsApp Cloud API

### Por que Meta Cloud API?

| Critério | Decisão |
|---|---|
| Custo | Gratuito até 1.000 conversas/mês (muito acima do necessário para 5 usuários) |
| Oficialidade | API oficial Meta — sem risco de banimento |
| Número | Meta fornece número de teste gratuito (sem chip necessário) |
| Destinatários | Até 5 números cadastrados manualmente no modo de teste |
| Setup | ~1 dia de configuração |

---

## Fluxo da conversa (máquina de estados)

```
Usuário envia vídeo ou áudio
        │
        ▼
Bot salva o media_id e pergunta:
┌─────────────────────────────┐
│ 👋 Olá! Recebi seu vídeo.   │
│ O que você quer fazer?      │
│                             │
│ 1️⃣  Só transcrever          │
│ 2️⃣  Transcrever + Resumir   │
└─────────────────────────────┘
        │
  ┌─────┴─────┐
  │ "1"       │ "2"
  ▼           ▼
[WAITING_  [WAITING_MODEL]
 FORMAT]
             Bot pergunta:
        ┌──────────────────────┐
        │ Qual modelo de IA?   │
        │                      │
        │ 1️⃣ Groq · Llama 3.3  │
        │ 2️⃣ Gemini · Flash    │
        │ 3️⃣ Gemma 2 · 9B 💻   │
        │ 4️⃣ Qwen3 · 8B 💻     │
        └──────────────────────┘
                   │
                   ▼
            [WAITING_FORMAT]
             Bot pergunta:
        ┌──────────────────────┐
        │ Como quer receber?   │
        │                      │
        │ 1️⃣ Texto no WhatsApp  │
        │ 2️⃣ PDF nesta conversa │
        └──────────────────────┘
                   │
                   ▼
              [PROCESSING]
        "⏳ Processando seu vídeo..."
                   │
        ┌──────────┴──────────┐
        │ texto               │ pdf
        ▼                     ▼
 Envia mensagem         Gera PDF e envia
 de texto no WA         como documento no WA
```

### Estados da sessão por usuário

```python
sessions = {
    "+5511999990000": {
        "state":    "WAITING_MODEL",  # IDLE | WAITING_ACTION | WAITING_MODEL | WAITING_FORMAT | PROCESSING
        "media_id": "wamid.abc123",   # ID da mídia salva na API do Meta
        "action":   "summarize",      # "transcribe" | "summarize"
        "model":    None,             # "groq" | "gemini" | "gemma2" | "qwen3"
        "format":   None,             # "text" | "pdf"
        "expires":  1713200000        # TTL: sessão expira em 10 min sem resposta
    }
}
```

---

## Arquitetura técnica

```
app/
├── whatsapp.py      ← download de mídia + envio de mensagem + envio de PDF
├── audio.py         ← extração de áudio server-side com ffmpeg
├── session.py       ← máquina de estados (get/set/clear por número de telefone)
├── groq.py          ← já existe (transcrição Whisper)
├── summarizer.py    ← já existe (resumo Groq/Gemini/Ollama)
└── routes.py        ← novo endpoint /whatsapp/webhook (GET + POST)
```

### Novos endpoints Flask

```
GET  /whatsapp/webhook  → verificação de token pelo Meta (obrigatório)
POST /whatsapp/webhook  → recebe mensagens e processa o fluxo
```

### Variáveis de ambiente (.env)

```
WA_PHONE_NUMBER_ID=<ID do número no painel Meta>
WA_ACCESS_TOKEN=<token de acesso permanente>
WA_VERIFY_TOKEN=<string secreta que você escolhe>
```

### Dependências adicionais

```
ffmpeg      ← instalado no sistema (extração de áudio server-side)
pydub       ← pip (wrapper Python do ffmpeg)
fpdf2       ← pip (geração de PDF server-side para envio no WhatsApp)
```

---

## Configuração da Meta Cloud API (passo a passo)

### Etapa 1 — Contas

| O que | Onde | Custo |
|---|---|---|
| Conta Facebook pessoal | facebook.com | Grátis |
| Conta de desenvolvedor | developers.meta.com | Grátis |
| Portfólio de negócios | business.facebook.com | Grátis |

> O portfólio **não precisa ser empresa verificada** para o modo de teste.

### Etapa 2 — Criar o App

1. Acessar **developers.meta.com/apps**
2. Clicar em **"Criar app"** → tipo **"Negócios"**
3. Dar o nome `ResumeX` e associar ao portfólio
4. No painel do app → **"Adicionar produto"** → selecionar **WhatsApp**

### Etapa 3 — Número de telefone

- O Meta fornece um **número de teste gratuito** (sem precisar de chip)
- Cadastrar manualmente até **5 números de destinatários**
- Cada usuário precisa receber uma mensagem do número de teste uma vez para ativar a conversa

### Etapa 4 — Coletar credenciais

```
WA_PHONE_NUMBER_ID → Painel WhatsApp → "Números de telefone"
WA_ACCESS_TOKEN    → Painel → "Gerar token de acesso"
                     (para token permanente: Business Settings → Usuários do sistema)
WA_VERIFY_TOKEN    → Qualquer string secreta definida por você
```

### Etapa 5 — Webhook

**Desenvolvimento (PC local):**
```bash
ngrok http 8765
# Gera: https://abc123.ngrok-free.app
```

**Configurar no painel Meta:**
- WhatsApp → Configuração → Webhook
- URL: `https://abc123.ngrok-free.app/whatsapp/webhook`
- Token de verificação: valor do `WA_VERIFY_TOKEN`
- Campo inscrito: `messages`

**Produção:**
- Qualquer servidor com HTTPS (Railway, Render — ambos têm plano gratuito)

---

## Como o usuário aciona o bot

| Cenário | Como funciona |
|---|---|
| **Chat individual** | Qualquer mensagem ou mídia enviada ao número do bot aciona o webhook automaticamente |
| **Grupo** | Usuário envia a mídia e menciona `@ResumeX` na legenda; o bot inicia o fluxo em conversa privada para não poluir o grupo |

---

## Envio de PDF pelo WhatsApp

A Meta Cloud API suporta envio de documentos nativamente:

```
1. Gerar PDF em memória (BytesIO) com fpdf2
2. Upload do PDF para a API do Meta → recebe um media_id
3. Enviar mensagem do tipo "document" com esse media_id
→ Usuário recebe PDF baixável direto na conversa
```

---

## Sprint de implementação

```
Sprint 1 — Core do bot (3-4h)
  ├─ app/session.py     → máquina de estados em memória
  ├─ app/audio.py       → extração de áudio com ffmpeg
  ├─ app/whatsapp.py    → download de mídia + envio de mensagem
  └─ routes.py          → rota /whatsapp/webhook (GET + POST)

Sprint 2 — Processamento (2h)
  ├─ Ligar audio.py → groq.py → summarizer.py no fluxo do webhook
  └─ Geração de PDF server-side com fpdf2 + envio como documento

Sprint 3 — Testes end-to-end (1h)
  ├─ ngrok http 8765
  ├─ Configurar webhook no painel Meta
  ├─ Enviar vídeo real pelo WhatsApp
  └─ Ajustes de UX nas mensagens do bot
```

---

## Checklist para começar

```
[ ] Criar conta em developers.meta.com
[ ] Criar App do tipo "Negócios"
[ ] Adicionar produto WhatsApp ao app
[ ] Criar portfólio de negócios (se ainda não tiver)
[ ] Copiar Phone Number ID
[ ] Gerar Access Token permanente (via Usuário do sistema)
[ ] Definir WA_VERIFY_TOKEN (qualquer string secreta)
[ ] Baixar e instalar ngrok
[ ] Adicionar os 5 números de destinatários ao número de teste
[ ] Adicionar credenciais ao .env
[ ] Implementar sprint 1–3
```

---

*Documento gerado em 2026-04-14*  
*Projeto: ResumeX — Transcritor e Resumidor de Vídeo com IA*
