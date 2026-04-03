import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { FileSpreadsheet } from 'lucide-react'
import { toast } from 'sonner'
import { uploadFile } from '@/api'
import { useStore } from '@/store'

export function Step1Upload() {
  const [uploading, setUploading] = useState(false)
  const { setUploadResult, setStep } = useStore()

  const onDrop = useCallback(async (accepted: File[]) => {
    const file = accepted[0]
    if (!file) return
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (!['xlsx', 'xls', 'ofx'].includes(ext || '')) {
      toast.error('Only .xlsx, .xls, or .ofx files are accepted')
      return
    }
    setUploading(true)
    try {
      const data = await uploadFile(file)
      setUploadResult(data, file.name)
      setStep(2)
      toast.success('File uploaded and analysed')
    } catch (e: any) {
      toast.error(`Upload failed: ${e.message}`)
    } finally {
      setUploading(false)
    }
  }, [setUploadResult, setStep])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
      'application/x-ofx': ['.ofx'],
      'application/ofx': ['.ofx'],
      'text/plain': ['.ofx'],
    },
    multiple: false,
    disabled: uploading,
  })

  return (
    <div className="max-w-xl">
      <h2 className="text-lg font-bold mb-1 text-text">Upload Bank Statement</h2>
      <p className="text-muted text-sm mb-6">Supports Thai bank Excel statements and standard bank-account OFX files.</p>

      <div
        {...getRootProps()}
        className={[
          'border-2 border-dashed rounded-xl p-14 text-center cursor-pointer transition-all',
          isDragActive ? 'border-accent bg-accent/5' : 'border-border hover:border-accent/50',
          uploading ? 'opacity-50 cursor-not-allowed' : '',
        ].join(' ')}
      >
        <input {...getInputProps()} />
        {uploading ? (
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
            <p className="text-muted text-sm">Analysing file…</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <FileSpreadsheet size={44} className="text-muted" />
            <p className="text-text2 font-medium">Drop your statement file here</p>
            <p className="text-muted text-sm">
              or <span className="text-accent underline cursor-pointer">browse</span> to select
            </p>
            <p className="text-muted text-xs mt-1">.xlsx / .xls / .ofx · Investigation-ready import</p>
          </div>
        )}
      </div>
    </div>
  )
}
