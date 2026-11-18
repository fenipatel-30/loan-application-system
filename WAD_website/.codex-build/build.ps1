$source = 'C:\Users\fenip\Downloads\WAD_Project_Template.pptx'
$root = (Resolve-Path '.codex-build').Path
$unpack = Join-Path $root 'pptx-unpacked'
$out = Join-Path (Resolve-Path 'output').Path 'Loan_Approval_System_Project.pptx'
if (Test-Path $unpack) { Remove-Item -LiteralPath $unpack -Recurse -Force }
New-Item -ItemType Directory -Path $unpack | Out-Null
[System.IO.Compression.ZipFile]::ExtractToDirectory($source, $unpack)
$ns = [System.Xml.XmlNamespaceManager]::new([System.Xml.NameTable]::new())
$ns.AddNamespace('p','http://schemas.openxmlformats.org/presentationml/2006/main')
$ns.AddNamespace('a','http://schemas.openxmlformats.org/drawingml/2006/main')
function Set-ShapeText($doc, $shapeName, $texts) {
  $shape = $doc.SelectSingleNode("//p:sp[p:nvSpPr/p:cNvPr[@name='$shapeName']]", $ns)
  if (-not $shape) { throw "Missing shape: $shapeName" }
  $body = $shape.SelectSingleNode('p:txBody', $ns)
  $paras = @($body.SelectNodes('a:p', $ns))
$textParas = @($paras | Where-Object { (($_.SelectNodes('.//a:t', $ns) | ForEach-Object { $_.InnerText }) -join '') -ne '' })
  for ($i=0; $i -lt $texts.Count; $i++) {
    if ($i -ge $textParas.Count) { throw "Insufficient paragraphs in $shapeName for requested text: need $($texts.Count), have $($textParas.Count) at index $i" }
    $p = $textParas[$i]
    $runs = @($p.SelectNodes('.//a:t', $ns))
    if ($runs.Count -eq 0) {
      $run = $doc.CreateElement('a','r','http://schemas.openxmlformats.org/drawingml/2006/main')
      $t = $doc.CreateElement('a','t','http://schemas.openxmlformats.org/drawingml/2006/main')
      [void]$run.AppendChild($t); [void]$p.AppendChild($run); $runs = @($t)
    }
    $runs[0].InnerText = [string]$texts[$i]
    for ($j=1; $j -lt $runs.Count; $j++) { $runs[$j].InnerText = '' }
  }
  for ($i=$texts.Count; $i -lt $textParas.Count; $i++) { [void]$textParas[$i].ParentNode.RemoveChild($textParas[$i]) }
}
$titles = @('Project Overview','Key Features & UI','Live Demo Plan','Technical Architecture','API Integration and Basic Security Measures','Development & Reflection','LinkedIn Post')
$bodies = @(
  @('Project Title: Loan Approval System','Problem: Loan application details and status updates can be difficult to manage in one place.','Objective: Provide an online flow to submit loan requests and track their status.','Target Users: Loan applicants and lending team reviewers.','Team Members & Roles: [Add names and roles]'),
  @('Guided loan application with field validation','Account registration and sign-in','My Profile shows submitted applications and status','UI screens: Home, Application, Login/Register and Profile'),
  @('Register a new account, then sign in','Open Apply for Loan and complete applicant and loan details','Submit and view the application in My Profile','Show required-field and invalid-value messages','Review the initial “Application Submitted” status'),
  @('Frontend: HTML, CSS and JavaScript','Backend: Python standard-library HTTP server','Database: SQLite','Flow: Browser → Python API → SQLite','Tables: users, sessions and loan_applications'),
  @('API: register, login, logout, applications and profile','Flow: Browser request → Python handler → SQLite','Password storage: salted PBKDF2 with SHA-256 (310,000 iterations)','Sessions use HttpOnly cookies with SameSite=Strict','Input checks, parameterized SQL and clear error responses'),
  @('Methodology: iterative feature development','Tools: VS Code, browser, Python and SQLite','Challenge: keeping application status linked to the right account; solution: store account and application records in SQLite','Deployment: local run at http://127.0.0.1:8000; no public URL is recorded','Future scope: reviewer dashboard, document storage and deployment','Key learning: connect forms, API routes, sessions and relational data','GitHub repository (required): [Add repository URL]'),
  @('Excited to share my Loan Approval System, a web application for submitting and tracking loan applications.','The goal was to bring applicant details and application status into one simple online flow.','Applicants can create an account, choose a loan type, submit their details and review application status from their profile.','The project supports personal, home, education, business and vehicle loan requests.','Tech stack: HTML, CSS, JavaScript, Python and SQLite.','Building it helped me connect browser forms to API routes, database records and secure login sessions.','GitHub repository: [Add repository URL]','Live demo: Not deployed publicly','Feedback is welcome!')
)
for ($i=1; $i -le 7; $i++) {
  $path = Join-Path $unpack "ppt/slides/slide$i.xml"
  $doc = [System.Xml.XmlDocument]::new(); $doc.PreserveWhitespace = $true; $doc.Load($path)
  Set-ShapeText $doc 'Title 1' @($titles[$i-1])
  Set-ShapeText $doc 'Content Placeholder 2' $bodies[$i-1]
  $writerSettings = [System.Xml.XmlWriterSettings]::new(); $writerSettings.Encoding = [System.Text.UTF8Encoding]::new($false); $writerSettings.Indent = $false
  $writer = [System.Xml.XmlWriter]::Create($path, $writerSettings); $doc.Save($writer); $writer.Close()
}
if (Test-Path $out) { throw "Output already exists: $out" }
[System.IO.Compression.ZipFile]::CreateFromDirectory($unpack, $out, [System.IO.Compression.CompressionLevel]::Optimal, $false)
Get-Item $out | Select-Object FullName,Length



