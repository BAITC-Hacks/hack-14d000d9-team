import { useState } from 'react';
import type { ReviewItem } from '../types/chat';
export function UploadReview({items,onPrompt,disabled}:{items:ReviewItem[];onPrompt:(text:string)=>void;disabled:boolean}){
  const [rows,setRows]=useState(items);
  return <section className="upload-review"><strong>Проверьте распознанные позиции</strong><p>Исправьте артикулы и количество. После проверки потребуется отдельное подтверждение добавления.</p>
    {rows.map((row,index)=><div className="review-row" key={index}>
      <input aria-label={`Позиция ${index+1}`} value={row.query} onChange={e=>setRows(rows.map((r,i)=>i===index?{...r,query:e.target.value}:r))}/>
      <input aria-label={`Количество ${index+1}`} type="number" min={1} max={10000} value={row.quantity??''} onChange={e=>setRows(rows.map((r,i)=>i===index?{...r,quantity:e.target.value?Number(e.target.value):null}:r))}/>
      <small>{row.confidence}</small><button disabled={disabled||!row.query.trim()||!Number.isInteger(row.quantity)||Number(row.quantity)<1||Number(row.quantity)>10000} onClick={()=>onPrompt(`Добавь ${row.quantity} штуки ${row.query}`)}>Проверить и подготовить</button>
    </div>)}
  </section>;
}
