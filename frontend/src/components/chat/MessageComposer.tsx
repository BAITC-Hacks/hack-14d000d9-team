import { useRef, useState, type FormEvent, type DragEvent } from 'react';
import { ArrowUp, File, LoaderCircle, Paperclip, X } from 'lucide-react';

interface Props { isLoading: boolean; onSend: (content: string, files: File[]) => Promise<boolean> }
export function MessageComposer({ isLoading, onSend }: Props) {
  const [draft, setDraft] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState('');
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  function addFiles(incoming: File[]) {
    const next = [...files];
    const errors: string[] = [];
    for (const file of incoming) {
      if (file.size > 25 * 1024 * 1024) { errors.push(`${file.name}: больше 25 МБ`); continue; }
      if (next.some((f) => f.name === file.name && f.size === file.size && f.lastModified === file.lastModified)) continue;
      if (next.length >= 10 || next.reduce((sum, f) => sum + f.size, 0) + file.size > 50 * 1024 * 1024) { errors.push('До 10 файлов, суммарно до 50 МБ'); break; }
      next.push(file);
    }
    setFiles(next); setError(errors.join('. '));
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (isLoading || (!draft.trim() && !files.length)) return;
    if (await onSend(draft, files)) { setDraft(''); setFiles([]); setError(''); }
  }
  function drop(event: DragEvent) { event.preventDefault(); setDragging(false); if (!isLoading) addFiles(Array.from(event.dataTransfer.files)); }
  return <form className={`composer ${dragging ? 'is-dragging' : ''}`} onSubmit={submit} onDragOver={(e) => { e.preventDefault(); if (!isLoading) setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={drop}>
    {files.length > 0 && <div className="attachments">{files.map((file, index) => <div className="attachment" key={`${file.name}-${file.lastModified}`}><File size={15} /><span title={file.name}>{file.name}<small>{Math.max(1, Math.round(file.size / 1024))} КБ</small></span><button type="button" className="icon-button" disabled={isLoading} title="Удалить файл" aria-label={`Удалить ${file.name}`} onClick={() => setFiles(files.filter((_, i) => i !== index))}><X size={14} /></button></div>)}</div>}
    {error && <p className="error" role="alert">{error}</p>}
    <textarea aria-label="Сообщение помощнику" placeholder="Что ищете? Какой товар сравнить или подобрать?" value={draft} onChange={(e) => setDraft(e.target.value)} disabled={isLoading} rows={2} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); e.currentTarget.form?.requestSubmit(); } }} />
    <div className="composer-tools"><input ref={input} type="file" multiple hidden onChange={(e) => { addFiles(Array.from(e.target.files || [])); e.target.value = ''; }} disabled={isLoading} />
      <button type="button" className="icon-button" title="Прикрепить файлы любого формата" aria-label="Прикрепить файлы" disabled={isLoading} onClick={() => input.current?.click()}><Paperclip size={20} /></button>
      <small>{files.length ? `${files.length} файлов` : 'До 25 МБ на файл'}</small>
      <button className="send-button" type="submit" title="Отправить" aria-label="Отправить сообщение" disabled={isLoading || (!draft.trim() && !files.length)}>{isLoading ? <LoaderCircle size={19} className="spinner" /> : <ArrowUp size={20} />}</button>
    </div>
  </form>;
}
