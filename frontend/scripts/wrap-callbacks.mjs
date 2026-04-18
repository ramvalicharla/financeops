import fs from 'fs'
import path from 'path'

function getAllFiles(dir, exts) {
  let results = []
  const list = fs.readdirSync(dir)
  for (const file of list) {
    const full = path.join(dir, file)
    const stat = fs.statSync(full)
    if (stat.isDirectory() && !full.includes('node_modules') && !full.includes('.next')) {
      results = results.concat(getAllFiles(full, exts))
    } else if (exts.some(ext => file.endsWith(ext))) {
      results.push(full)
    }
  }
  return results
}

const dirs = ['./app', './components']
let allFiles = []
for (const d of dirs) {
  if (fs.existsSync(d)) allFiles = allFiles.concat(getAllFiles(d, ['.tsx', '.ts']))
}

// Function names to wrap
const funcNames = ['load', 'loadAll', 'loadContributor', 'refreshCount']

let totalFixed = 0

for (const file of allFiles) {
  let src = fs.readFileSync(file, 'utf8')
  let changed = false

  for (const fn of funcNames) {
    // Match: const fn = async (...) => {
    // We need to find the matching closing brace then check if useEffect uses it
    const pattern = new RegExp(`(  const ${fn} = async [^=]*=> \\{)`)
    if (!pattern.test(src)) continue
    if (src.includes(`useCallback(async`)) continue // Already wrapped

    // Split into lines for brace counting
    const lines = src.split('\n')
    let startLine = -1
    let startMatch = null

    for (let i = 0; i < lines.length; i++) {
      const m = lines[i].match(new RegExp(`^  const ${fn} = async ([^=]*)=> \\{`))
      if (m) {
        startLine = i
        startMatch = m
        break
      }
    }

    if (startLine === -1) continue

    // Count braces to find end
    let depth = 0
    let endLine = -1
    for (let i = startLine; i < lines.length; i++) {
      for (const ch of lines[i]) {
        if (ch === '{') depth++
        if (ch === '}') {
          depth--
          if (depth === 0) {
            endLine = i
            break
          }
        }
      }
      if (endLine !== -1) break
    }

    if (endLine === -1) continue

    // Extract the body (lines between start and end inclusive)
    const bodyLines = lines.slice(startLine, endLine + 1)
    const bodyStr = bodyLines.join('\n')

    // Extract dep from useEffect that calls this fn
    const effectPattern = new RegExp(`useEffect\\(\\(\\) => \\{[\\s\\S]*?void ${fn}\\(\\)[\\s\\S]*?\\}, \\[([^\\]]*)\\]\\)`)
    const effectMatch = src.match(effectPattern)
    
    // Build useCallback dep array
    // Collect the existing useEffect deps and remove the fn name itself
    let existingDeps = ''
    let newEffectDeps = ''
    if (effectMatch) {
      existingDeps = effectMatch[1].trim()
      // The useCallback gets the existing deps (minus fn name), useEffect gets [...deps, fn]
      newEffectDeps = existingDeps ? `${existingDeps}, ${fn}` : fn
    } else {
      newEffectDeps = fn
    }

    // Build new wrapped version
    const originalDecl = lines[startLine]
    const argsMatch = originalDecl.match(new RegExp(`const ${fn} = async (.*?)=> \\{`))
    const args = argsMatch ? argsMatch[1].trim() : '() '

    // Replace the function declaration: wrap body lines in useCallback
    const newBodyLines = [...bodyLines]
    // Change first line: "  const fn = async () => {" -> "  const fn = useCallback(async () => {"
    newBodyLines[0] = newBodyLines[0].replace(
      new RegExp(`const ${fn} = async`),
      `const ${fn} = useCallback(async`
    )
    // Change last line: "  }" -> "  }, [deps])"
    newBodyLines[newBodyLines.length - 1] = newBodyLines[newBodyLines.length - 1].replace(
      /^  \}$/,
      `  }, [${existingDeps}])`
    )

    const newBodyStr = newBodyLines.join('\n')
    const newSrc = src.replace(bodyStr, newBodyStr)

    // Update useEffect dep array  
    let finalSrc = newSrc
    if (effectMatch && existingDeps !== undefined) {
      finalSrc = finalSrc.replace(
        new RegExp(`(useEffect\\(\\(\\) => \\{[\\s\\S]*?void ${fn}\\(\\)[\\s\\S]*?\\}, \\[)([^\\]]*)(\\]\\))`),
        (match, before, deps, after) => {
          const cleanDeps = deps.trim()
          if (cleanDeps.includes(fn)) return match
          return `${before}${cleanDeps ? cleanDeps + ', ' : ''}${fn}${after}`
        }
      )
    }

    if (finalSrc !== src) {
      src = finalSrc
      changed = true
      totalFixed++
    }
  }

  if (changed) {
    fs.writeFileSync(file, src, 'utf8')
  }
}

console.log(`useCallback wrappers applied: ${totalFixed} functions`)
