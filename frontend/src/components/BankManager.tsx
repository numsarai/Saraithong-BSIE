import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { getBanks, getBank, createBank, deleteBank, getBankLogoCatalog } from '@/api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardTitle } from '@/components/ui/card'
import { BankLogo } from '@/components/BankLogo'
import { toast } from 'sonner'
import { Plus, Trash2, X, ChevronLeft, Building2, Save } from 'lucide-react'

const LOGICAL_FIELDS = [
  'date','time','description','amount','debit','credit',
  'balance','channel','counterparty_account','counterparty_name',
  'sender_account','sender_name','receiver_account','receiver_name',
]

const FIELD_LABEL_KEYS: Record<string, string> = {
  date: 'bankManager.fields.date',
  time: 'bankManager.fields.time',
  description: 'bankManager.fields.description',
  amount: 'bankManager.fields.amount',
  debit: 'bankManager.fields.debit',
  credit: 'bankManager.fields.credit',
  balance: 'bankManager.fields.balance',
  channel: 'bankManager.fields.channel',
  counterparty_account: 'bankManager.fields.counterpartyAccount',
  counterparty_name: 'bankManager.fields.counterpartyName',
  sender_account: 'bankManager.fields.senderAccount',
  sender_name: 'bankManager.fields.senderName',
  receiver_account: 'bankManager.fields.receiverAccount',
  receiver_name: 'bankManager.fields.receiverName',
}

type BankCfg = {
  key: string
  bank_name: string
  sheet_index: number
  header_row: number
  format_type: string
  amount_mode: string
  column_mapping: Record<string, string[]>
  logo_url?: string
  template_source?: string
  is_builtin?: boolean
  has_template?: boolean
  template_badge?: string
  bank_type?: string
  bank_name_th?: string
  bank_name_en?: string
  head_office_address?: string
}

type BankBrand = {
  key: string
  name: string
  logo_url?: string
  template_source?: string
  has_template?: boolean
  template_badge?: string
  bank_type?: string
  is_builtin?: boolean
  bank_name_th?: string
  bank_name_en?: string
  head_office_address?: string
}

const EMPTY_CFG: BankCfg = {
  key: '', bank_name: '', sheet_index: 0, header_row: 0,
  format_type: 'standard', amount_mode: 'signed', column_mapping: {},
}

export function BankManager() {
  const { t } = useTranslation()
  const { data: banks = [], refetch } = useQuery({ queryKey: ['banks'], queryFn: getBanks })
  const { data: bankCatalog = [], refetch: refetchCatalog } = useQuery({ queryKey: ['bank-logo-catalog'], queryFn: getBankLogoCatalog })
  const [selected, setSelected]   = useState<BankCfg | null>(null)
  const [editMode, setEditMode]   = useState(false)
  const [form, setForm]           = useState<BankCfg>(EMPTY_CFG)
  const [newAlias, setNewAlias]   = useState<Record<string,string>>({})
  const [delConfirm, setDelConfirm] = useState<string | null>(null)

  const openBank = async (key: string) => {
    try {
      const cfg = await getBank(key)
      setSelected(cfg)
      setForm({ ...cfg })
      setEditMode(false)
    } catch (e: any) { toast.error(e.message) }
  }

  const handleSave = async () => {
    if (!form.key.trim())       { toast.error(t('bankManager.toast.keyRequired')); return }
    if (!form.bank_name.trim()) { toast.error(t('bankManager.toast.nameRequired')); return }
    try {
      const saved = await createBank(form)
      await refetch()
      await refetchCatalog()
      toast.success(t('bankManager.toast.saved'))
      setEditMode(false)
      setSelected({
        ...form,
        ...(saved?.logo || {}),
        bank_name: form.bank_name,
        has_template: true,
        template_source: 'custom',
        is_builtin: false,
      })
    } catch (e: any) { toast.error(e.message) }
  }

  const handleDelete = async (key: string) => {
    try {
      await deleteBank(key)
      await refetch()
      await refetchCatalog()
      toast.success(t('bankManager.toast.deleted'))
      setSelected(null)
      setDelConfirm(null)
    } catch (e: any) { toast.error(e.message) }
  }

  const addAlias = (field: string) => {
    const v = (newAlias[field] || '').trim()
    if (!v) return
    const cur = form.column_mapping[field] || []
    if (!cur.includes(v)) {
      setForm(f => ({ ...f, column_mapping: { ...f.column_mapping, [field]: [...cur, v] } }))
    }
    setNewAlias(a => ({ ...a, [field]: '' }))
  }

  const removeAlias = (field: string, alias: string) => {
    setForm(f => ({
      ...f,
      column_mapping: {
        ...f.column_mapping,
        [field]: (f.column_mapping[field] || []).filter(a => a !== alias),
      },
    }))
  }

  const startNew = () => {
    setSelected(null)
    setForm(EMPTY_CFG)
    setEditMode(true)
  }

  const startPrepared = (bank: BankBrand) => {
    setSelected(null)
    setForm({
      ...EMPTY_CFG,
      key: bank.key,
      bank_name: bank.name,
      bank_name_th: bank.bank_name_th,
      bank_name_en: bank.bank_name_en,
      head_office_address: bank.head_office_address,
      logo_url: bank.logo_url,
      template_source: 'custom',
      is_builtin: false,
      has_template: false,
      template_badge: bank.template_badge,
      bank_type: bank.bank_type,
    })
    setEditMode(true)
  }

  const preparedBanks = bankCatalog.filter((bank: BankBrand) => !bank.has_template && bank.bank_type === 'thai_bank')

  return (
    <div className="flex gap-6 min-h-[80vh]">
      {/* Left panel — bank list */}
      <div className="w-56 shrink-0 space-y-2">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-bold text-text flex items-center gap-2">
            <Building2 size={15} className="text-accent" />{t('bankManager.title')}
          </h3>
          <Button size="sm" variant="primary" onClick={startNew}><Plus size={12} />{t('bankManager.new')}</Button>
        </div>
        {banks.map((b: BankBrand) => (
          <div
            key={b.key}
            onClick={() => openBank(b.key)}
            className={[
              'flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-all text-sm',
              selected?.key === b.key
                ? 'bg-accent/15 text-accent border border-accent/30'
                : 'bg-surface2 text-text2 border border-border hover:border-accent/40 hover:text-accent',
            ].join(' ')}
          >
            <BankLogo bank={b} size="sm" />
            <span className="flex-1 truncate">{b.name}</span>
            {(b.is_builtin || b.template_source === 'builtin')
              ? <Badge variant="gray">{t('bankManager.builtin')}</Badge>
              : <Badge variant="blue">{t('bankManager.custom')}</Badge>
            }
          </div>
        ))}
        {preparedBanks.length > 0 && (
          <>
            <div className="mt-5 pt-4 border-t border-border/70">
              <div className="mb-2 text-[11px] uppercase tracking-wide text-muted font-semibold">{t('bankManager.thaiBanksPrepared')}</div>
              <div className="space-y-2">
                {preparedBanks.map((b: BankBrand) => (
                  <div
                    key={b.key}
                    onClick={() => startPrepared(b)}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-all text-sm bg-surface2/60 text-text2 border border-border hover:border-accent/40 hover:text-accent"
                  >
                    <BankLogo bank={b} size="sm" />
                    <span className="flex-1 truncate">{b.name}</span>
                    <Badge variant="yellow">{t('bankManager.logoReady')}</Badge>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Right panel — detail/edit */}
      <div className="flex-1">
        {/* New Bank form */}
        {editMode && !selected && (
          <BankForm
            form={form} setForm={setForm}
            newAlias={newAlias} setNewAlias={setNewAlias}
            addAlias={addAlias} removeAlias={removeAlias}
            onSave={handleSave}
            onCancel={() => setEditMode(false)}
            isNew
          />
        )}

        {/* View / Edit existing */}
        {selected && (
          editMode
            ? <BankForm
                form={form} setForm={setForm}
                newAlias={newAlias} setNewAlias={setNewAlias}
                addAlias={addAlias} removeAlias={removeAlias}
                onSave={handleSave}
                onCancel={() => { setEditMode(false); setForm({ ...selected }) }}
                isNew={false}
              />
            : <BankDetail
                bank={selected}
                isBuiltin={!!selected.is_builtin || selected.template_source === 'builtin'}
                onEdit={() => { setForm({ ...selected }); setEditMode(true) }}
                onDelete={() => setDelConfirm(selected.key)}
              />
        )}

        {!editMode && !selected && (
          <div className="flex flex-col items-center justify-center h-full text-muted gap-3 pt-20">
            <Building2 size={40} className="opacity-20" />
            <p className="text-sm">{t('bankManager.selectBank')}</p>
            <Button variant="outline" onClick={startNew}><Plus size={13} />{t('bankManager.addNewBank')}</Button>
          </div>
        )}
      </div>

      {/* Delete confirmation */}
      {delConfirm && (
        <div className="fixed inset-0 bg-black/75 z-50 flex items-center justify-center p-4"
          onClick={() => setDelConfirm(null)}>
          <div className="bg-surface border border-border rounded-xl p-6 w-full max-w-[380px] shadow-2xl"
            onClick={e => e.stopPropagation()}>
            <h3 className="text-base font-bold text-danger mb-2">{t('bankManager.deleteBank')}</h3>
            <p className="text-sm text-text2 mb-5">
              {t('bankManager.deleteConfirm')} <span className="text-text font-semibold">"{delConfirm}"</span>{t('bankManager.cannotUndo')}
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setDelConfirm(null)}>{t('bankManager.cancel')}</Button>
              <Button variant="danger" onClick={() => handleDelete(delConfirm!)}>
                <Trash2 size={13} />{t('common.delete')}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/* ── Bank Detail view ─────────────────────────────────────────────────── */
function BankDetail({ bank, isBuiltin, onEdit, onDelete }: {
  bank: BankCfg; isBuiltin: boolean; onEdit: () => void; onDelete: () => void
}) {
  const { t } = useTranslation()

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3">
          <BankLogo bank={{ key: bank.key, name: bank.bank_name, logo_url: bank.logo_url }} size="lg" />
          <div>
          <div className="flex items-center gap-2 mb-1">
            <h2 className="text-xl font-bold text-text">{bank.bank_name}</h2>
            <Badge variant={isBuiltin ? 'gray' : 'blue'}>{isBuiltin ? t('bankManager.builtin') : t('bankManager.custom')}</Badge>
            {bank.template_badge && <Badge variant="yellow">{bank.template_badge}</Badge>}
          </div>
          <p className="text-muted text-sm">{t('bankManager.bankKey')}: <span className="font-mono text-text2">{bank.key}</span></p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={onEdit}>{t('bankManager.edit')}</Button>
          {!isBuiltin && (
            <Button size="sm" variant="danger" onClick={onDelete}><Trash2 size={12} />{t('common.delete')}</Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3">
        {[
          { label: t('bankManager.formatType'),  value: bank.format_type },
          { label: t('bankManager.amountMode'),  value: bank.amount_mode },
          { label: t('bankManager.sheetIndex'),  value: String(bank.sheet_index) },
          { label: t('bankManager.headerRowLabel'),   value: String(bank.header_row) },
        ].map(({ label, value }) => (
          <Card key={label} className="!p-3">
            <div className="text-[10px] uppercase text-muted font-semibold mb-1">{label}</div>
            <div className="text-sm font-mono text-text">{value}</div>
          </Card>
        ))}
      </div>

      <ReferenceProfile bank={bank} />

      <Card>
        <CardTitle>{t('bankManager.columnAliases')}</CardTitle>
        <div className="space-y-2">
          {LOGICAL_FIELDS.map(field => {
            const aliases = bank.column_mapping?.[field] || []
            if (!aliases.length) return null
            return (
              <div key={field} className="flex items-start gap-3 py-1.5 border-b border-border/40 last:border-0">
                <span className="text-[11px] uppercase text-muted font-semibold w-40 shrink-0 pt-0.5">
                  {FIELD_LABEL_KEYS[field] ? t(FIELD_LABEL_KEYS[field]) : field}
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {aliases.map(a => (
                    <span key={a} className="text-xs bg-surface2 border border-border px-2 py-0.5 rounded-full text-text2 font-mono">
                      {a}
                    </span>
                  ))}
                </div>
              </div>
            )
          })}
          {Object.keys(bank.column_mapping || {}).length === 0 && (
            <p className="text-sm text-muted">{t('bankManager.noAliases')}</p>
          )}
        </div>
      </Card>
    </div>
  )
}

/* ── Bank Form (create/edit) ──────────────────────────────────────────── */
function BankForm({ form, setForm, newAlias, setNewAlias, addAlias, removeAlias, onSave, onCancel, isNew }: {
  form: BankCfg
  setForm: (f: BankCfg) => void
  newAlias: Record<string,string>
  setNewAlias: (a: Record<string,string>) => void
  addAlias: (field: string) => void
  removeAlias: (field: string, alias: string) => void
  onSave: () => void
  onCancel: () => void
  isNew: boolean
}) {
  const { t } = useTranslation()

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <BankLogo bank={{ key: form.key, name: form.bank_name || form.key, logo_url: form.logo_url }} size="lg" />
          <div>
            <h2 className="text-lg font-bold text-text">{isNew ? t('bankManager.addNewBank') : `${t('bankManager.edit')}: ${form.bank_name}`}</h2>
            {form.template_badge && <p className="text-xs text-muted">{form.template_badge}</p>}
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={onCancel}><ChevronLeft size={13} />{t('bankManager.cancel')}</Button>
          <Button variant="success" size="sm" onClick={onSave}><Save size={13} />{t('bankManager.saveBank')}</Button>
        </div>
      </div>

      {/* Basic info */}
      <Card>
        <CardTitle>Basic Info</CardTitle>
        <div className="grid grid-cols-2 gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-[11px] uppercase text-muted font-semibold">{t('bankManager.bankKey')} <span className="text-danger">*</span></label>
            <input value={form.key}
              onChange={e => setForm({ ...form, key: e.target.value.toLowerCase().replace(/\s+/g,'_') })}
              disabled={!isNew}
              placeholder="e.g. mybank"
              className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none disabled:opacity-50"
            />
            <span className="text-[10px] text-muted">{t('bankManager.bankKeyHint')}</span>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] uppercase text-muted font-semibold">{t('bankManager.bankName')} <span className="text-danger">*</span></label>
            <input value={form.bank_name}
              onChange={e => setForm({ ...form, bank_name: e.target.value })}
              placeholder="e.g. Bangkok Bank"
              className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] uppercase text-muted font-semibold">{t('bankManager.formatType')}</label>
            <select value={form.format_type}
              onChange={e => setForm({ ...form, format_type: e.target.value })}
              className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none cursor-pointer">
              <option value="standard">{t('bankManager.form.formatTypeStandard')}</option>
              <option value="dual_account">{t('bankManager.form.amountModeDualAccount')}</option>
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] uppercase text-muted font-semibold">{t('bankManager.amountMode')}</label>
            <select value={form.amount_mode}
              onChange={e => setForm({ ...form, amount_mode: e.target.value })}
              className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none cursor-pointer">
              <option value="signed">{t('bankManager.form.amountModeSigned')}</option>
              <option value="debit_credit">{t('bankManager.form.amountModeDebitCredit')}</option>
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] uppercase text-muted font-semibold">{t('bankManager.sheetIndex')}</label>
            <input type="number" min={0} value={form.sheet_index}
              onChange={e => setForm({ ...form, sheet_index: Number(e.target.value) })}
              className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none w-24"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] uppercase text-muted font-semibold">{t('bankManager.headerRowLabel')}</label>
            <input type="number" min={0} value={form.header_row}
              onChange={e => setForm({ ...form, header_row: Number(e.target.value) })}
              className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none w-24"
            />
          </div>
        </div>
      </Card>

      <ReferenceProfile bank={form} />

      {/* Column aliases */}
      <Card>
        <CardTitle>{t('bankManager.columnAliases')}</CardTitle>
        <p className="text-xs text-muted mb-4">
          {t('bankManager.aliasHint')}
        </p>
        <div className="space-y-3">
          {LOGICAL_FIELDS.map(field => {
            const aliases = form.column_mapping?.[field] || []
            return (
              <div key={field} className="border border-border/50 rounded-lg p-3 bg-surface2/30">
                <div className="text-[11px] uppercase text-muted font-semibold mb-2">
                  {FIELD_LABEL_KEYS[field] ? t(FIELD_LABEL_KEYS[field]) : field}
                </div>
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {aliases.map(a => (
                    <span key={a} className="flex items-center gap-1 text-xs bg-surface3 border border-border px-2 py-0.5 rounded-full text-text2 font-mono">
                      {a}
                      <button onClick={() => removeAlias(field, a)}
                        className="text-muted hover:text-danger transition-colors ml-0.5">
                        <X size={10} />
                      </button>
                    </span>
                  ))}
                  {aliases.length === 0 && (
                    <span className="text-xs text-muted italic">{t('bankManager.noAliasField')}</span>
                  )}
                </div>
                <div className="flex gap-2">
                  <input
                    value={newAlias[field] || ''}
                    onChange={e => setNewAlias({ ...newAlias, [field]: e.target.value })}
                    onKeyDown={e => { if (e.key === 'Enter') addAlias(field) }}
                    placeholder={t('bankManager.aliasPlaceholder')}
                    className="bg-surface2 border border-border rounded-lg px-2 py-1 text-xs text-text focus:border-accent outline-none flex-1 max-w-[260px]"
                  />
                  <Button size="sm" variant="ghost" onClick={() => addAlias(field)}>
                    <Plus size={11} />Add
                  </Button>
                </div>
              </div>
            )
          })}
        </div>
      </Card>
    </div>
  )
}

function ReferenceProfile({ bank }: { bank: Pick<BankCfg, 'bank_name_th' | 'bank_name_en' | 'head_office_address'> }) {
  const { t } = useTranslation()

  const referenceRows = [
    { label: t('bankManager.referenceProfile.thaiName'), value: bank.bank_name_th },
    { label: t('bankManager.referenceProfile.englishName'), value: bank.bank_name_en },
    { label: t('bankManager.referenceProfile.headOffice'), value: bank.head_office_address },
  ].filter((row) => row.value)

  if (referenceRows.length === 0) return null

  return (
    <Card>
      <CardTitle>Reference Profile</CardTitle>
      <div className="space-y-2">
        {referenceRows.map((row) => (
          <div key={row.label} className="flex items-start gap-3 py-1.5 border-b border-border/40 last:border-0">
            <span className="text-[11px] uppercase text-muted font-semibold w-36 shrink-0 pt-0.5">
              {row.label}
            </span>
            <span className="text-sm text-text2 break-words">{row.value}</span>
          </div>
        ))}
      </div>
    </Card>
  )
}
