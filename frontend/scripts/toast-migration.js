const fs = require('fs')
const path = require('path')

function walkDir(dir, callback) {
  fs.readdirSync(dir).forEach(f => {
    let dirPath = path.join(dir, f)
    let isDirectory = fs.statSync(dirPath).isDirectory()
    if (isDirectory && !dirPath.includes('node_modules') && !dirPath.includes('.next')) {
        walkDir(dirPath, callback)
    } else if (f.endsWith('PageClient.tsx')) {
        callback(dirPath)
    }
  })
}

function processFile(filePath) {
  let content = fs.readFileSync(filePath, 'utf8')
  if (!content.includes('setMessage(')) return

  // 1. Remove useState for message
  content = content.replace(/const \[message, setMessage\] = useState[^\n]+\n/g, '')
  
  // 2. Remove {message ? ... : null} blocks
  content = content.replace(/\{message \? <[^>]+>\{message\}<\/[^>]+> : null\}\n?/g, '')
  content = content.replace(/\{message \? \(\s*<[^>]+>\s*\{message\}\s*<\/[^>]+>\s*\)\s*: null\}\n?/g, '')
  content = content.replace(/\{message && <[^>]+>\{message\}<\/[^>]+>\}\n?/g, '')

  // 3. Replace setMessage(null) with nothing OR a comment if inline
  content = content.replace(/setMessage\(null\);?\n?/g, '')
  
  // 4. Replace setMessage("foo") with toast.success("foo")
  content = content.replace(/setMessage\(([^)]+)\)/g, 'toast.success($1)')

  // 5. Add sonner import if not present
  if (!content.includes("import { toast } from 'sonner'") && !content.includes('import { toast } from "sonner"')) {
    // find last import
    const lastImportIndex = content.lastIndexOf('import ')
    if (lastImportIndex !== -1) {
      const newLineIndex = content.indexOf('\n', lastImportIndex)
      content = content.slice(0, newLineIndex) + '\nimport { toast } from "sonner"' + content.slice(newLineIndex)
    } else {
      content = 'import { toast } from "sonner"\n' + content
    }
  }

  // 6. Clean up any leftover message variables in dependencies
  content = content.replace(/message,/g, '')
  content = content.replace(/, message/g, '')

  fs.writeFileSync(filePath, content, 'utf8')
  console.log('Migrated toast patterns in', filePath)
}

walkDir('./app', processFile)
