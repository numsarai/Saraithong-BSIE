import { useState, useRef, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Bot, Send, Loader2, Trash2, Sparkles, AlertCircle, Paperclip, X } from 'lucide-react'
import { llmChat, getLlmStatus } from '@/api'

interface LlmChatProps {
  /** Account number to provide as context */
  account?: string
  /** Transaction rows to include as RAG context */
  transactions?: any[]
  /** Compact mode — smaller height for embedding in pages */
  compact?: boolean
}

interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: number
}

const QUICK_PROMPTS = [
  { key: 'summarize', icon: Sparkles },
  { key: 'suspicious', icon: AlertCircle },
]

export function LlmChat({ account, transactions, compact }: LlmChatProps) {
  const { t } = useTranslation()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [ollamaOnline, setOllamaOnline] = useState<boolean | null>(null)
  const [modelName, setModelName] = useState('')
  const [attachedFile, setAttachedFile] = useState<File | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Check Ollama status on mount
  useEffect(() => {
    getLlmStatus()
      .then((data) => {
        setOllamaOnline(data.status === 'ok')
        if (data.models?.length) setModelName(data.models[0])
      })
      .catch(() => setOllamaOnline(false))
  }, [])

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const sendMessage = useCallback(async (text: string) => {
    if ((!text.trim() && !attachedFile) || loading) return

    const label = attachedFile ? `${text.trim()} [${attachedFile.name}]` : text.trim()
    const userMsg: ChatMessage = { role: 'user', content: label, timestamp: Date.now() }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      let result: any

      if (attachedFile) {
        // Multimodal: send file to /api/llm/analyze-file
        const fd = new FormData()
        fd.append('file', attachedFile)
        fd.append('message', text.trim() || 'วิเคราะห์เอกสารนี้ สรุปข้อมูลที่พบ')
        const resp = await fetch('/api/llm/analyze-file', { method: 'POST', body: fd })
        if (!resp.ok) throw new Error(await resp.text())
        result = await resp.json()
        setAttachedFile(null)
      } else {
        // Text-only: use regular chat with DB context
        result = await llmChat(text.trim(), {
          account: account || undefined,
          transactions: transactions?.slice(0, 50) || undefined,
        })
      }

      const assistantMsg: ChatMessage = {
        role: 'assistant',
        content: result.response || 'ไม่ได้รับคำตอบ',
        timestamp: Date.now(),
      }
      setMessages(prev => [...prev, assistantMsg])
    } catch (err: unknown) {
      const errorMsg: ChatMessage = {
        role: 'system',
        content: err instanceof Error ? err.message : 'เกิดข้อผิดพลาดในการเชื่อมต่อ LLM',
        timestamp: Date.now(),
      }
      setMessages(prev => [...prev, errorMsg])
    } finally {
      setLoading(false)
    }
  }, [loading, account, transactions, attachedFile])

  const handleQuickPrompt = (key: string) => {
    const prompts: Record<string, string> = {
      summarize: 'สรุปภาพรวมธุรกรรมของบัญชีนี้ ครอบคลุมยอดเงินเข้า-ออก คู่สัญญาหลัก และรูปแบบที่น่าสงสัย',
      suspicious: 'ตรวจสอบว่ามีรูปแบบผิดปกติหรือไม่ เช่น ฟอกเงิน แบ่งรายการ บัญชีตัวกลาง',
    }
    sendMessage(prompts[key] || '')
  }

  const height = compact ? 'h-80' : 'h-[480px]'

  return (
    <Card className="p-4 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Bot size={18} className="text-accent" />
          <CardTitle className="text-text text-sm">{t('llm.title')}</CardTitle>
        </div>
        <div className="flex items-center gap-2">
          {ollamaOnline !== null && (
            <span className={`flex items-center gap-1 text-[10px] ${ollamaOnline ? 'text-success' : 'text-danger'}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${ollamaOnline ? 'bg-success' : 'bg-danger'}`} />
              {ollamaOnline ? modelName || 'Online' : 'Offline'}
            </span>
          )}
          {messages.length > 0 && (
            <button onClick={() => setMessages([])} className="text-muted hover:text-text cursor-pointer p-1" title={t('llm.clear')}>
              <Trash2 size={12} />
            </button>
          )}
        </div>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className={`${height} overflow-y-auto mb-3 space-y-3 pr-1`}>
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Bot size={32} className="text-muted mb-2 opacity-40" />
            <p className="text-muted text-sm">{t('llm.hint')}</p>
            {account && (
              <p className="text-muted text-xs mt-1">
                {t('llm.contextAccount')}: <span className="font-mono text-text">{account}</span>
                {transactions?.length ? ` (${transactions.length} ${t('llm.txns')})` : ''}
              </p>
            )}
            {/* Quick prompts */}
            <div className="flex gap-2 mt-4">
              {QUICK_PROMPTS.map(({ key, icon: Icon }) => (
                <button
                  key={key}
                  onClick={() => handleQuickPrompt(key)}
                  disabled={!ollamaOnline || loading}
                  className="flex items-center gap-1.5 rounded-lg border border-border bg-surface2 px-3 py-1.5 text-xs text-muted hover:text-text hover:border-accent/40 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <Icon size={12} />
                  {t(`llm.quick.${key}`)}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={[
              'max-w-[85%] rounded-lg px-3 py-2 text-sm leading-relaxed',
              msg.role === 'user'
                ? 'bg-accent/15 text-text border border-accent/20'
                : msg.role === 'system'
                  ? 'bg-danger/10 text-danger border border-danger/20'
                  : 'bg-surface2 text-text2 border border-border',
            ].join(' ')}>
              {msg.role === 'assistant' && (
                <div className="flex items-center gap-1 mb-1 text-[10px] text-muted">
                  <Bot size={10} /> AI
                </div>
              )}
              <div className="whitespace-pre-wrap text-xs">{msg.content}</div>
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="rounded-lg bg-surface2 border border-border px-3 py-2 flex items-center gap-2 text-muted text-sm">
              <Loader2 size={14} className="animate-spin" />
              {t('llm.thinking')}
            </div>
          </div>
        )}
      </div>

      {/* Attached file indicator */}
      {attachedFile && (
        <div className="flex items-center gap-2 mb-2 px-1">
          <span className="inline-flex items-center gap-1.5 rounded-lg bg-accent/10 border border-accent/20 px-2.5 py-1 text-xs text-accent">
            <Paperclip size={11} />
            {attachedFile.name}
            <button onClick={() => setAttachedFile(null)} className="hover:text-danger cursor-pointer"><X size={11} /></button>
          </span>
        </div>
      )}

      {/* Input */}
      <div className="flex gap-2">
        <input
          ref={fileInputRef}
          type="file"
          accept="image/png,image/jpeg,image/webp,image/bmp,.pdf,.xlsx,.xls,.csv"
          className="hidden"
          onChange={e => { const f = e.target.files?.[0]; if (f) setAttachedFile(f); e.target.value = '' }}
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={!ollamaOnline || loading}
          className="shrink-0 rounded-lg border border-border bg-surface2 p-2 text-muted hover:text-accent hover:border-accent/40 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          title={t('llm.attachFile')}
        >
          <Paperclip size={16} />
        </button>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(input) } }}
          placeholder={ollamaOnline ? t('llm.placeholder') : t('llm.offline')}
          disabled={!ollamaOnline || loading}
          className="flex-1 rounded-lg border border-border bg-surface2 px-3 py-2 text-sm text-text outline-none focus:border-accent disabled:opacity-40"
        />
        <Button
          variant="success"
          onClick={() => sendMessage(input)}
          disabled={(!input.trim() && !attachedFile) || !ollamaOnline || loading}
        >
          <Send size={14} />
        </Button>
      </div>
    </Card>
  )
}
