"use client"
import { useCallback, useState } from "react"
import { useDropzone } from "react-dropzone"
import { motion, AnimatePresence } from "framer-motion"
import { Upload, FileText, CheckCircle, XCircle, Loader } from "lucide-react"
import { useUploadInvoice } from "@/hooks/useInvoices"
import { fileSizeFmt } from "@/lib/utils"

export function InvoiceUpload({ onClose }: { onClose?: () => void }) {
  const { mutate: upload, isPending, isSuccess, isError, progress } = useUploadInvoice()
  const [file, setFile] = useState<File | null>(null)

  const onDrop = useCallback((accepted: File[]) => {
    if (!accepted[0]) return
    setFile(accepted[0])
    upload(accepted[0])
  }, [upload])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"], "image/png": [".png"], "image/jpeg": [".jpg", ".jpeg"] },
    maxSize: 20 * 1024 * 1024,
    multiple: false,
    disabled: isPending || isSuccess,
  })

  return (
    <div style={{ padding: "24px", minWidth: 420 }}>
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 15, fontWeight: 600, color: "var(--text-1)" }}>Upload Invoice</div>
        <div style={{ fontSize: 12.5, color: "var(--text-3)", marginTop: 3 }}>PDF, PNG or JPEG · max 20 MB</div>
      </div>

      <div {...getRootProps()} className={`upload-zone${isDragActive ? " drag-over" : ""}`}>
        <input {...getInputProps()}/>
        <AnimatePresence mode="wait">
          {!file && !isPending && !isSuccess && !isError && (
            <motion.div key="idle" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
              <div style={{ width: 48, height: 48, borderRadius: 12, background: "var(--bg-4)", border: "1px solid var(--border)", display: "grid", placeItems: "center" }}>
                <Upload size={22} style={{ color: "var(--accent)" }}/>
              </div>
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: 13.5, color: "var(--text-1)", fontWeight: 500 }}>
                  {isDragActive ? "Drop to upload" : "Drag & drop or click to browse"}
                </div>
                <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 4 }}>Invoice will be queued for OCR extraction</div>
              </div>
            </motion.div>
          )}

          {(file && isPending) && (
            <motion.div key="uploading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
              <FileText size={32} style={{ color: "var(--accent)" }}/>
              <div style={{ fontSize: 13, color: "var(--text-1)", fontWeight: 500 }}>{file.name}</div>
              <div style={{ fontSize: 11.5, color: "var(--text-3)" }}>{fileSizeFmt(file.size)}</div>
              <div style={{ width: "100%", maxWidth: 280 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--text-3)", marginBottom: 4 }}>
                  <span>Uploading…</span><span>{progress}%</span>
                </div>
                <div style={{ height: 4, background: "var(--bg-4)", borderRadius: 999, overflow: "hidden" }}>
                  <motion.div
                    style={{ height: "100%", background: "var(--accent)", borderRadius: 999 }}
                    animate={{ width: `${progress}%` }}
                    transition={{ duration: 0.3 }}
                  />
                </div>
              </div>
            </motion.div>
          )}

          {isSuccess && (
            <motion.div key="success" initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
              style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
              <CheckCircle size={36} style={{ color: "var(--success)" }}/>
              <div style={{ fontSize: 13.5, color: "var(--text-1)", fontWeight: 500 }}>Uploaded successfully</div>
              <div style={{ fontSize: 12, color: "var(--text-3)" }}>OCR processing started in background</div>
            </motion.div>
          )}

          {isError && (
            <motion.div key="error" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
              <XCircle size={36} style={{ color: "var(--danger)" }}/>
              <div style={{ fontSize: 13.5, color: "var(--text-1)", fontWeight: 500 }}>Upload failed</div>
              <div style={{ fontSize: 12, color: "var(--text-3)" }}>Check file type, size limit (20 MB), and try again</div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div style={{ display: "flex", gap: 8, marginTop: 16, justifyContent: "flex-end" }}>
        {onClose && (
          <button className="btn btn-sm" onClick={onClose}>
            {isSuccess ? "Close" : "Cancel"}
          </button>
        )}
        {isError && (
          <button className="btn btn-sm btn-primary" onClick={() => setFile(null)}>
            Try again
          </button>
        )}
      </div>
    </div>
  )
}
