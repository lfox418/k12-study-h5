import katex from 'katex'

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

/**
 * 将包含 $$...$$（块级）与 $...$（行内）的混合文本安全渲染为 HTML
 */
export function renderLatexText(raw) {
  if (!raw) return ''
  // 先拆分块级公式 $$...$$
  const blockParts = String(raw).split(/(\$\$[\s\S]+?\$\$)/g)
  return blockParts
    .map((part) => {
      if (part.startsWith('$$') && part.endsWith('$$')) {
        const expr = part.slice(2, -2).trim()
        try {
          return katex.renderToString(expr, { displayMode: true, throwOnError: false })
        } catch {
          return escapeHtml(part)
        }
      }
      // 再拆分行内公式 $...$
      const inlineParts = part.split(/(\$[^$\n]+?\$)/g)
      return inlineParts
        .map((seg) => {
          if (seg.startsWith('$') && seg.endsWith('$')) {
            const expr = seg.slice(1, -1).trim()
            try {
              return katex.renderToString(expr, { displayMode: false, throwOnError: false })
            } catch {
              return escapeHtml(seg)
            }
          }
          // 支持简单粗体 **text** 与换行
          return escapeHtml(seg)
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br/>')
        })
        .join('')
    })
    .join('')
}
