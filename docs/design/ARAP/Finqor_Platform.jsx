import React, { useState, useMemo, useEffect } from "react";
import {
  FileText, Receipt, ShoppingCart, CreditCard, Layers, Activity, Shield,
  CheckCircle2, AlertTriangle, XCircle, ChevronRight, Upload, Sparkles,
  Database, GitBranch, Lock, Eye, Zap, Bot, FileCheck, AlertOctagon,
  ArrowRight, Search, Settings, Users, DollarSign, TrendingUp, Clock,
  Building2, Banknote, FileSignature, BookOpen, Globe, Package,
  ChevronDown, Info, Play, Send, ArrowDown, ArrowUp, Filter,
  Hash, Calendar, Tag, MapPin
} from "lucide-react";

/* =====================================================================
   FINQOR PLATFORM — 4-Module Accounting Layer
   M1 Invoicing  |  M2 AR-Collections  |  M3 Expense-P2P  |  M4 AP-Bills/Pay
   Shared: CoA, Dimensions, Calendar, FX, Tax, Audit, IAM, AI agents
   ===================================================================== */

// ---------------------- DESIGN TOKENS ----------------------
const C = {
  bg:      "#0B0F14",
  panel:   "#11171F",
  panel2:  "#161D27",
  border:  "#1F2A37",
  borderL: "#2A3645",
  ink:     "#E6EDF3",
  ink2:    "#9BA8B8",
  ink3:    "#5F6C7E",
  navy:    "#0F2A4A",
  brand:   "#D4A24C", // muted gold
  brand2:  "#E9C078",
  green:   "#3FB37F",
  red:     "#E5484D",
  amber:   "#F0A23A",
  blue:    "#4A8DD3",
  violet:  "#8B7FD3",
};

// ---------------------- SAMPLE DATA -----------------------
// One canonical AP invoice document and one AR invoice transaction power the demo.

const apDocument = {
  filename: "STELLAR_INV_7791.pdf",
  vendor: "Stellar Components Ltd",
  vendorTaxId: "07AABCS9876B1Z9",
  invoiceNo: "STL-INV-7791",
  invoiceDate: "2026-04-22",
  postingDate: "2026-04-25",
  dueDate: null, // intentionally missing — gap engine will catch
  currency: "INR",
  poRef: "PO-2026-1184",
  grnRef: "GRN-2026-2204",
  // intentionally missing: segment, project, beneficial_owner, contract_ref
  lines: [
    { ln:1, item:"Server XR-200",     poQty:50, grnQty:50, invQty:50, poPrice:85000.00, invPrice:85000.00 },
    { ln:2, item:"Storage Disk 4TB",  poQty:20, grnQty:20, invQty:20, poPrice:18000.00, invPrice:18500.00 }, // price var
    { ln:3, item:"Network Switch 48", poQty:10, grnQty:8,  invQty:10, poPrice:42000.00, invPrice:42000.00 }, // qty var
  ]
};

const arDocument = {
  customer: "Acme Industries Pvt Ltd",
  customerTaxId: "07AABCA1234C1Z5",
  invoiceNo: "INV-2026-04-0091",
  invoiceDate: "2026-04-25",
  dueDate: "2026-05-25",
  currency: "INR",
  soRef: "SO-2026-1184",
  deliveryRef: "DN-2026-9921",
  performanceObligation: "Point-in-time",
  lines: [
    { ln:1, item:"Server XR-200",       hsn:"8471",   qty:2,  price:145000, disc:0, taxCode:"GST-IGST-18" },
    { ln:2, item:"Implementation 40hr", hsn:"998313", qty:40, price:2500,   disc:5, taxCode:"GST-IGST-18" },
    { ln:3, item:"Storage Disk 4TB",    hsn:"8523",   qty:4,  price:18000,  disc:0, taxCode:"GST-IGST-18" },
  ]
};

// $1B-company "completeness" rules — gap-engine reference
const billionDollarFields = {
  ap: [
    { id:"vendor",         label:"Vendor (master-resolved)",            critical:true,  why:"E/O assertion, sanctions screening" },
    { id:"vendorBank",     label:"Vendor bank (master-locked)",         critical:true,  why:"Anti-BEC; payment routing" },
    { id:"invoiceNo",      label:"Vendor invoice number",               critical:true,  why:"Duplicate detection key" },
    { id:"invoiceDate",    label:"Invoice date",                        critical:true,  why:"Tax point, ageing, period assignment" },
    { id:"dueDate",        label:"Due date / payment term",             critical:true,  why:"Ageing, discount-capture, cash forecast" },
    { id:"poRef",          label:"PO reference",                        critical:true,  why:"3-way match, commitment release" },
    { id:"grnRef",         label:"GRN / SES reference",                 critical:true,  why:"3-way match, accrual reversal" },
    { id:"currency",       label:"Currency",                            critical:true,  why:"FX revaluation, hedge accounting" },
    { id:"costCentre",     label:"Cost centre",                         critical:true,  why:"Mgmt reporting, budget-actual" },
    { id:"profitCentre",   label:"Profit centre",                       critical:true,  why:"Segment reporting (IFRS 8)" },
    { id:"segment",        label:"Operating segment",                   critical:true,  why:"IFRS 8 / Ind-AS 108 disclosure" },
    { id:"project",        label:"Project / WBS",                       critical:false, why:"Project costing, capex tracking" },
    { id:"taxCode",        label:"Input tax code (per line)",           critical:true,  why:"GST/VAT recoverability, tax return" },
    { id:"whtCode",        label:"WHT / TDS section (per line)",        critical:true,  why:"Statutory deduction, certificate" },
    { id:"hsnSac",         label:"HSN / SAC code",                      critical:true,  why:"Tax determination, e-invoice" },
    { id:"contractRef",    label:"Contract / MSA reference",            critical:true,  why:"Obligation linkage, audit trail" },
    { id:"beneficialOwner",label:"Beneficial-ownership confirmed",      critical:true,  why:"AML, sanctions, FATCA" },
    { id:"countryOfOrigin",label:"Country of origin (goods)",           critical:false, why:"Customs, FTA preferential rate" },
    { id:"icPartner",      label:"Inter-company partner flag",          critical:true,  why:"Consolidation elimination" },
    { id:"transferPricing",label:"Transfer-pricing arm-length flag",    critical:true,  why:"OECD BEPS, local-file" },
  ],
  ar: [
    { id:"customer",       label:"Customer (master-resolved)",          critical:true,  why:"E/O, credit limit, sanctions" },
    { id:"creditCheck",    label:"Credit-limit check passed",           critical:true,  why:"R&O, exposure mgmt" },
    { id:"invoiceNo",      label:"Invoice number",                      critical:true,  why:"Numbering integrity, statutory" },
    { id:"invoiceDate",    label:"Invoice date",                        critical:true,  why:"Tax point, recognition trigger" },
    { id:"dueDate",        label:"Due date",                            critical:true,  why:"Ageing, ECL bucket" },
    { id:"currency",       label:"Currency + FX rate",                  critical:true,  why:"Revaluation, IAS 21" },
    { id:"soRef",          label:"Sales order reference",               critical:true,  why:"Order-to-cash linkage" },
    { id:"deliveryRef",    label:"Delivery / proof of delivery",        critical:true,  why:"Revenue recognition (IFRS 15)" },
    { id:"performanceObligation", label:"Performance obligation type",  critical:true,  why:"IFRS 15 — point-in-time vs over-time" },
    { id:"placeOfSupply",  label:"Place of supply (tax)",               critical:true,  why:"GST/VAT jurisdiction" },
    { id:"hsnSac",         label:"HSN / SAC per line",                  critical:true,  why:"Tax rate, e-invoice" },
    { id:"costCentre",     label:"Cost centre",                         critical:true,  why:"Mgmt reporting" },
    { id:"profitCentre",   label:"Profit centre",                       critical:true,  why:"Segment (IFRS 8)" },
    { id:"segment",        label:"Operating segment",                   critical:true,  why:"IFRS 8 disclosure" },
    { id:"project",        label:"Project / WBS",                       critical:false, why:"Project revenue tracking" },
    { id:"contractRef",    label:"Contract reference (IFRS 15)",        critical:true,  why:"Obligation allocation" },
    { id:"icCustomer",     label:"Inter-company flag",                  critical:true,  why:"Consolidation elimination" },
    { id:"eInvoiceJurisd", label:"E-invoice jurisdiction tag",          critical:true,  why:"IRP/SDI/ZATCA/PEPPOL clearance" },
    { id:"incoterms",      label:"INCOTERMS",                           critical:false, why:"Title transfer, cut-off" },
    { id:"deferredFlag",   label:"Deferred-revenue flag",               critical:true,  why:"IFRS 15 contract liability" },
  ]
};

// AI agents (cross-module)
const aiAgents = [
  { id:"agt-extract",  name:"Extraction Agent",       icon:FileCheck,   modules:["M1","M3"], desc:"Multi-format OCR + LLM parse → canonical schema; confidence per field" },
  { id:"agt-resolve",  name:"Master-Data Resolver",   icon:Database,    modules:["M1","M3"], desc:"Fuzzy + deterministic match on customer/vendor/item/GL/dim" },
  { id:"agt-gap",      name:"Gap-Detection Agent",    icon:Search,      modules:["M1","M3"], desc:"Compares populated fields vs $1B-co completeness rules; surfaces gaps" },
  { id:"agt-anomaly",  name:"Anomaly Agent",          icon:AlertOctagon,modules:["M1","M2","M3","M4"], desc:"Detects duplicates, BEC patterns, ghost-vendor, PR/PO splitting, payment fraud" },
  { id:"agt-match",    name:"Match Agent",            icon:GitBranch,   modules:["M3"],      desc:"Three-way / four-way line-level match; tolerance learning over time" },
  { id:"agt-approver", name:"Approval-Predict Agent", icon:Users,       modules:["M3","M4"], desc:"Predicts next approver from history + DOA + delegation rules" },
  { id:"agt-tax",      name:"Tax Agent",              icon:Globe,       modules:["M1","M3"], desc:"GST/VAT/RCM/WHT determination + e-invoice clearance routing" },
  { id:"agt-cashapp",  name:"Cash-App Agent",         icon:Banknote,    modules:["M2"],      desc:"95%+ STP receipts → invoice match using ML on payee/amount/ref/history" },
  { id:"agt-ecl",      name:"ECL Agent",              icon:TrendingUp,  modules:["M2"],      desc:"IFRS 9 expected credit loss with predicted-payment-date model" },
  { id:"agt-collect",  name:"Collections Agent",      icon:Send,        modules:["M2"],      desc:"Predicts late payment, sequences dunning, drafts customer outreach" },
  { id:"agt-paymentopt",name:"Payment-Optim Agent",   icon:CreditCard,  modules:["M4"],      desc:"Method routing (RTGS/ACH/SEPA/V-card), discount capture, FX netting" },
  { id:"agt-controls", name:"Controls Agent",         icon:Shield,      modules:["M1","M2","M3","M4"], desc:"Runs SoD, period-open, balance, sanctions, threshold checks at posting" },
];

// Modules
const modules = [
  {
    id:"M1", code:"M1", name:"Invoicing & E-Invoice",
    cycle:"Revenue", color:C.brand, icon:Receipt,
    desc:"Customer invoice creation, IFRS 15 recognition, tax determination, IRP/PEPPOL clearance, dispatch.",
    inputs:["Sales order / contract", "Delivery / POD", "Time-sheet / usage", "Milestone certificate"],
    outputs:["Customer invoice", "Credit / debit note", "E-invoice IRN+QR", "Revenue JE → CoA"],
    keyControls:["AR-C04 Credit limit", "AR-C08 IFRS 15 PO rule", "AR-C09 Tax engine", "AR-C10 IRP clearance", "AR-C12 Σ Dr=Cr"],
    posts:["Dr Trade Receivables", "Cr Revenue (line GL)", "Cr Output Tax", "Cr Deferred Revenue (if applicable)"]
  },
  {
    id:"M2", code:"M2", name:"AR — Collections & Cash App",
    cycle:"Revenue", color:C.green, icon:Banknote,
    desc:"Bank-statement ingest, ML cash application, dunning, disputes, write-off, IFRS 9 ECL.",
    inputs:["Bank stmt MT940/CAMT.053/BAI2", "Lockbox file", "Customer remittance advice", "Dispute notification"],
    outputs:["Allocated receipt", "Dunning letter", "Credit memo", "ECL run", "Write-off"],
    keyControls:["AR-C14 Auto-match 95%", "AR-C15 Unapplied ageing", "AR-C18 Dunning escalation", "AR-C21 Write-off DOA", "AR-C22 ECL matrix"],
    posts:["Dr Cash / Bank", "Cr Trade Receivables", "Dr/Cr FX gain/loss", "Dr Bad-debt expense / Cr ECL provision"]
  },
  {
    id:"M3", code:"M3", name:"Expense & P2P",
    cycle:"Expenditure", color:C.blue, icon:ShoppingCart,
    desc:"PR → PO → GRN → invoice 3-way/4-way match → approval. Includes employee T&E and corporate card.",
    inputs:["Purchase requisition", "PO", "GRN / SES", "Vendor invoice", "Expense receipt", "Card statement"],
    outputs:["Matched invoice", "Match exception", "Approved bill ready for AP", "Period-end accrual"],
    keyControls:["AP-C06 PR DOA", "AP-C11 GRN SoD", "AP-C17 3-way match", "AP-C20 DOA approval", "AP-C40 GR/IR ageing"],
    posts:["Dr Expense / Inventory / Asset", "Dr Input Tax", "Cr GR/IR (clearing)", "Cr Trade Payables (on match)"]
  },
  {
    id:"M4", code:"M4", name:"AP — Bills & Payments",
    cycle:"Expenditure", color:C.violet, icon:CreditCard,
    desc:"Payment proposal, dual-control release, ISO 20022 file, positive-pay, sanctions, vendor recon.",
    inputs:["Approved invoice (from M3)", "Vendor master bank", "Bank rates", "Sanctions feed"],
    outputs:["Payment proposal", "ISO 20022 pain.001 / NACHA / SEPA", "Payment run", "Vendor stmt recon"],
    keyControls:["AP-C28 Payment from approved", "AP-C29 Dual-control release", "AP-C30 Dup-payment", "AP-C31 Positive-pay", "AP-C34 Sanctions"],
    posts:["Dr Trade Payables", "Cr Cash / Bank", "Dr/Cr Discount Earned", "Dr/Cr FX gain/loss"]
  },
];

// ----- helpers -----
const fmt = n => n == null ? "—" : n.toLocaleString("en-IN", {minimumFractionDigits:2, maximumFractionDigits:2});
const fmt0 = n => n == null ? "—" : n.toLocaleString("en-IN");

// =====================================================================
// COMPONENT: Header
// =====================================================================
function Header({ activeModule, setActiveModule }) {
  return (
    <header style={{
      position:"sticky", top:0, zIndex:50,
      borderBottom:`1px solid ${C.border}`,
      background:`${C.bg}E6`, backdropFilter:"blur(12px)",
    }}>
      <div style={{padding:"14px 28px", display:"flex", alignItems:"center", justifyContent:"space-between"}}>
        <div style={{display:"flex", alignItems:"center", gap:14}}>
          <div style={{
            width:36, height:36, borderRadius:8,
            background:`linear-gradient(135deg, ${C.brand} 0%, ${C.brand2} 100%)`,
            display:"flex", alignItems:"center", justifyContent:"center",
            boxShadow:`0 4px 14px ${C.brand}55`,
          }}>
            <Layers size={18} color={C.navy} strokeWidth={2.5}/>
          </div>
          <div>
            <div style={{fontSize:18, fontWeight:700, letterSpacing:"-0.02em", color:C.ink, fontFamily:"'IBM Plex Serif', Georgia, serif"}}>FINQOR</div>
            <div style={{fontSize:10, color:C.ink3, letterSpacing:"0.18em", fontFamily:"'JetBrains Mono', monospace"}}>ACCOUNTING LAYER · v1.0</div>
          </div>
        </div>
        <nav style={{display:"flex", gap:4}}>
          {[
            {id:"overview", label:"Overview"},
            {id:"M1", label:"M1 · Invoicing"},
            {id:"M2", label:"M2 · AR"},
            {id:"M3", label:"M3 · Expense"},
            {id:"M4", label:"M4 · AP"},
            {id:"agents", label:"AI Agents"},
            {id:"controls", label:"Controls"},
            {id:"flow", label:"E2E Flow"},
          ].map(m => (
            <button key={m.id} onClick={()=>setActiveModule(m.id)}
              style={{
                padding:"8px 14px", borderRadius:6, border:"none",
                background: activeModule===m.id ? C.panel2 : "transparent",
                color: activeModule===m.id ? C.brand2 : C.ink2,
                fontSize:12, fontWeight: activeModule===m.id ? 600 : 500,
                fontFamily:"'JetBrains Mono', monospace", cursor:"pointer",
                letterSpacing:"0.02em",
                transition:"all 150ms",
              }}>
              {m.label}
            </button>
          ))}
        </nav>
        <div style={{display:"flex", alignItems:"center", gap:14}}>
          <div style={{display:"flex", alignItems:"center", gap:8, padding:"6px 12px", border:`1px solid ${C.border}`, borderRadius:6}}>
            <div style={{width:6, height:6, borderRadius:"50%", background:C.green, boxShadow:`0 0 8px ${C.green}`}}/>
            <span style={{fontSize:11, color:C.ink2, fontFamily:"'JetBrains Mono', monospace"}}>SAP S/4 · CONNECTED</span>
          </div>
        </div>
      </div>
    </header>
  );
}

// =====================================================================
// COMPONENT: SectionCard (reusable)
// =====================================================================
function Card({title, subtitle, children, accent=C.brand, action}){
  return (
    <div style={{
      background:C.panel, border:`1px solid ${C.border}`, borderRadius:10,
      overflow:"hidden",
    }}>
      <div style={{padding:"14px 18px", borderBottom:`1px solid ${C.border}`, display:"flex", alignItems:"center", justifyContent:"space-between"}}>
        <div>
          <div style={{display:"flex", alignItems:"center", gap:10}}>
            <div style={{width:3, height:14, background:accent, borderRadius:2}}/>
            <h3 style={{margin:0, fontSize:13, fontWeight:600, color:C.ink, letterSpacing:"-0.005em"}}>{title}</h3>
          </div>
          {subtitle && <p style={{margin:"4px 0 0 13px", fontSize:11, color:C.ink3}}>{subtitle}</p>}
        </div>
        {action}
      </div>
      <div style={{padding:18}}>{children}</div>
    </div>
  );
}

function Pill({children, color=C.ink2, bg}){
  return (
    <span style={{
      display:"inline-flex", alignItems:"center", gap:5,
      padding:"3px 8px", borderRadius:4,
      background: bg || `${color}1A`, color,
      fontSize:10, fontFamily:"'JetBrains Mono', monospace",
      fontWeight:600, letterSpacing:"0.02em",
      border:`1px solid ${color}33`,
    }}>{children}</span>
  );
}

// =====================================================================
// VIEW: Overview (architecture diagram, 4 modules, agents, scale)
// =====================================================================
function OverviewView({setActiveModule}) {
  return (
    <div style={{padding:"28px 28px 60px"}}>
      {/* Hero */}
      <div style={{maxWidth:920, marginBottom:32}}>
        <div style={{fontSize:11, color:C.brand, fontFamily:"'JetBrains Mono', monospace", letterSpacing:"0.2em", marginBottom:14}}>
          FINQOR · ACCOUNTING LAYER · 4 MODULES · 12 AGENTS
        </div>
        <h1 style={{
          fontSize:46, lineHeight:1.05, margin:"0 0 16px", letterSpacing:"-0.03em", color:C.ink,
          fontFamily:"'IBM Plex Serif', Georgia, serif", fontWeight:500,
        }}>
          Document <span style={{color:C.brand, fontStyle:"italic"}}>in</span>. <br/>
          Balanced journal <span style={{color:C.brand, fontStyle:"italic"}}>out</span>. <br/>
          Audit-ready by design.
        </h1>
        <p style={{fontSize:15, lineHeight:1.55, color:C.ink2, margin:"0 0 24px", maxWidth:680}}>
          Four modules, one accounting layer. Every document — a vendor invoice in your inbox,
          a customer PO in EDI, a corporate-card statement, a bank file — flows through extraction →
          gap-detection → master resolution → control checks → balanced journal → ERP. SOX, COSO,
          ISO, IFRS controls run on every transaction; the gap-engine never lets a $1B-company
          field slip through silently.
        </p>
        <div style={{display:"flex", gap:10, flexWrap:"wrap"}}>
          <Pill color={C.brand}>SOX 404 native</Pill>
          <Pill color={C.green}>IFRS 15 / 9 / 16</Pill>
          <Pill color={C.blue}>SAP · Oracle · NetSuite · D365</Pill>
          <Pill color={C.violet}>e-Invoice IRP / PEPPOL / SDI / ZATCA</Pill>
          <Pill color={C.amber}>ISO 27001 / 27701</Pill>
        </div>
      </div>

      {/* Architecture */}
      <Card title="Platform architecture" subtitle="Shared accounting layer feeds & is fed by 4 specialised modules" accent={C.brand}>
        <ArchitectureDiagram setActiveModule={setActiveModule}/>
      </Card>

      <div style={{height:24}}/>

      {/* Module quick-cards */}
      <div style={{display:"grid", gridTemplateColumns:"repeat(2, 1fr)", gap:16}}>
        {modules.map(m => (
          <button key={m.id} onClick={()=>setActiveModule(m.id)} style={{
            textAlign:"left", border:`1px solid ${C.border}`, background:C.panel,
            borderRadius:10, padding:20, cursor:"pointer", transition:"all 200ms",
            color:"inherit",
          }}
            onMouseEnter={e=>{e.currentTarget.style.borderColor=m.color; e.currentTarget.style.transform="translateY(-2px)";}}
            onMouseLeave={e=>{e.currentTarget.style.borderColor=C.border; e.currentTarget.style.transform="none";}}
          >
            <div style={{display:"flex", alignItems:"flex-start", justifyContent:"space-between", marginBottom:14}}>
              <div style={{display:"flex", alignItems:"center", gap:12}}>
                <div style={{width:38, height:38, borderRadius:8, background:`${m.color}1A`, border:`1px solid ${m.color}55`,
                  display:"flex", alignItems:"center", justifyContent:"center"}}>
                  <m.icon size={18} color={m.color}/>
                </div>
                <div>
                  <div style={{fontSize:10, color:m.color, fontFamily:"'JetBrains Mono', monospace", fontWeight:600, letterSpacing:"0.1em"}}>
                    {m.code} · {m.cycle.toUpperCase()}
                  </div>
                  <div style={{fontSize:16, fontWeight:600, color:C.ink, marginTop:2}}>{m.name}</div>
                </div>
              </div>
              <ChevronRight size={16} color={C.ink3}/>
            </div>
            <p style={{margin:"0 0 14px", fontSize:12, color:C.ink2, lineHeight:1.5}}>{m.desc}</p>
            <div style={{display:"flex", flexWrap:"wrap", gap:6}}>
              {m.keyControls.slice(0,3).map(c=> <Pill key={c} color={C.ink3}>{c}</Pill>)}
              <Pill color={m.color}>+{m.keyControls.length-3} more</Pill>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

// Architecture diagram (SVG)
function ArchitectureDiagram({setActiveModule}) {
  return (
    <svg viewBox="0 0 1100 480" style={{width:"100%", height:"auto", display:"block"}}>
      <defs>
        <linearGradient id="layerGrad" x1="0" x2="1">
          <stop offset="0" stopColor={C.brand} stopOpacity="0.15"/>
          <stop offset="1" stopColor={C.brand} stopOpacity="0.05"/>
        </linearGradient>
        <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M0,0 L10,5 L0,10 z" fill={C.ink3}/>
        </marker>
      </defs>

      {/* Documents in (top) */}
      <g>
        <rect x="40" y="20" width="1020" height="56" rx="6" fill={C.panel2} stroke={C.border}/>
        <text x="60" y="44" fill={C.ink3} fontSize="10" fontFamily="'JetBrains Mono', monospace" letterSpacing="0.1em">SOURCE DOCUMENTS · ANY CHANNEL</text>
        {["Email", "Upload", "EDI 810/850", "PEPPOL UBL", "Bank MT940", "OCR mobile", "API", "Vendor portal"].map((d,i)=>(
          <g key={d}>
            <rect x={60 + i*120} y={52} width={106} height={20} rx={3} fill={C.panel} stroke={C.border}/>
            <text x={60 + i*120 + 53} y={66} fill={C.ink2} fontSize="10" textAnchor="middle">{d}</text>
          </g>
        ))}
      </g>

      {/* AI Agent Layer */}
      <g>
        <rect x="40" y="100" width="1020" height="64" rx="6" fill="url(#layerGrad)" stroke={C.brand} strokeOpacity="0.4"/>
        <text x="60" y="124" fill={C.brand} fontSize="10" fontFamily="'JetBrains Mono', monospace" letterSpacing="0.1em">AI AGENT LAYER · 12 AGENTS</text>
        {["Extract","Resolve","Gap-detect","Anomaly","Match","Approver","Tax","Cash-app","ECL","Collect","Pay-optim","Controls"].map((a,i)=>(
          <g key={a}>
            <rect x={60 + i*82} y={134} width={72} height={22} rx={3} fill={`${C.brand}22`} stroke={`${C.brand}55`}/>
            <text x={60 + i*82 + 36} y={149} fill={C.brand2} fontSize="9" textAnchor="middle" fontFamily="'JetBrains Mono', monospace">{a}</text>
          </g>
        ))}
      </g>

      {/* 4 modules */}
      <g>
        {modules.map((m,i)=>{
          const x = 60 + i*250;
          return (
            <g key={m.id} style={{cursor:"pointer"}} onClick={()=>setActiveModule(m.id)}>
              <rect x={x} y={190} width={220} height={90} rx={6}
                    fill={`${m.color}15`} stroke={m.color} strokeWidth="1.5"/>
              <text x={x+15} y={213} fill={m.color} fontSize="10" fontFamily="'JetBrains Mono', monospace" fontWeight="700" letterSpacing="0.1em">{m.code} · {m.cycle.toUpperCase()}</text>
              <text x={x+15} y={236} fill={C.ink} fontSize="14" fontWeight="600">{m.name}</text>
              <text x={x+15} y={258} fill={C.ink2} fontSize="10">{m.inputs.length} input types</text>
              <text x={x+15} y={272} fill={C.ink2} fontSize="10">{m.posts.length} JE legs · {m.keyControls.length} key controls</text>
            </g>
          );
        })}
      </g>

      {/* Inter-module flow arrows: M1 ↔ M2, M3 → M4 */}
      <line x1="280" y1="245" x2="305" y2="245" stroke={C.ink3} strokeWidth="1" markerEnd="url(#arr)"/>
      <line x1="305" y1="252" x2="280" y2="252" stroke={C.ink3} strokeWidth="1" markerEnd="url(#arr)"/>
      <line x1="780" y1="245" x2="805" y2="245" stroke={C.ink3} strokeWidth="1" markerEnd="url(#arr)"/>

      {/* Accounting layer */}
      <g>
        <rect x="40" y="305" width="1020" height="68" rx="6" fill={C.navy} stroke={C.brand} strokeOpacity="0.4"/>
        <text x="60" y="328" fill={C.brand2} fontSize="10" fontFamily="'JetBrains Mono', monospace" letterSpacing="0.1em">SHARED ACCOUNTING LAYER</text>
        {["Chart of Accounts", "Dimensions (CC/PC/Project/Segment)", "Calendar / Periods", "FX Rates", "Tax Engine", "Audit Trail", "IAM + SoD", "Evidence Vault"].map((s,i)=>(
          <g key={s}>
            <rect x={60 + i*120} y={341} width={106} height={22} rx={3} fill={`${C.brand}15`} stroke={`${C.brand}33`}/>
            <text x={60 + i*120 + 53} y={356} fill={C.brand2} fontSize="10" textAnchor="middle">{s}</text>
          </g>
        ))}
      </g>

      {/* TB / GL / ERP */}
      <g>
        <rect x="40" y="395" width="1020" height="64" rx="6" fill={C.panel2} stroke={C.green} strokeOpacity="0.45"/>
        <text x="60" y="418" fill={C.green} fontSize="10" fontFamily="'JetBrains Mono', monospace" letterSpacing="0.1em">TB / GL / CoA · CONNECTED ERP</text>
        {["SAP S/4HANA", "Oracle Fusion", "NetSuite", "MS Dynamics 365", "Custom (REST)", "Idempotent post", "Reconciled sub-ledger"].map((s,i)=>(
          <g key={s}>
            <rect x={60 + i*138} y={431} width={124} height={22} rx={3} fill={C.panel} stroke={C.border}/>
            <text x={60 + i*138 + 62} y={446} fill={C.ink2} fontSize="10" textAnchor="middle">{s}</text>
          </g>
        ))}
      </g>

      {/* Vertical arrows */}
      <line x1="550" y1="76" x2="550" y2="100" stroke={C.ink3} strokeWidth="1" markerEnd="url(#arr)"/>
      <line x1="550" y1="164" x2="550" y2="190" stroke={C.ink3} strokeWidth="1" markerEnd="url(#arr)"/>
      <line x1="550" y1="280" x2="550" y2="305" stroke={C.ink3} strokeWidth="1" markerEnd="url(#arr)"/>
      <line x1="550" y1="373" x2="550" y2="395" stroke={C.ink3} strokeWidth="1" markerEnd="url(#arr)"/>
    </svg>
  );
}

// =====================================================================
// VIEW: Module detail
// =====================================================================
function ModuleView({moduleId, setActiveModule}) {
  const m = modules.find(x => x.id === moduleId);
  if (!m) return null;

  return (
    <div style={{padding:"28px 28px 60px"}}>
      <button onClick={()=>setActiveModule("overview")} style={{
        background:"none", border:"none", color:C.ink3, fontSize:11,
        fontFamily:"'JetBrains Mono', monospace", cursor:"pointer", marginBottom:16,
        display:"inline-flex", alignItems:"center", gap:6,
      }}>
        ← BACK TO OVERVIEW
      </button>

      <div style={{display:"flex", alignItems:"flex-start", gap:18, marginBottom:28}}>
        <div style={{width:64, height:64, borderRadius:12, background:`${m.color}15`, border:`1px solid ${m.color}55`,
          display:"flex", alignItems:"center", justifyContent:"center"}}>
          <m.icon size={28} color={m.color}/>
        </div>
        <div>
          <div style={{fontSize:11, color:m.color, fontFamily:"'JetBrains Mono', monospace", fontWeight:600, letterSpacing:"0.15em"}}>
            {m.code} · {m.cycle.toUpperCase()} CYCLE
          </div>
          <h1 style={{margin:"4px 0 8px", fontSize:32, fontFamily:"'IBM Plex Serif', Georgia, serif", fontWeight:500, letterSpacing:"-0.02em", color:C.ink}}>{m.name}</h1>
          <p style={{margin:0, fontSize:14, color:C.ink2, maxWidth:780, lineHeight:1.55}}>{m.desc}</p>
        </div>
      </div>

      <div style={{display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:16, marginBottom:16}}>
        <Card title="Inputs" accent={m.color}>
          <ul style={{margin:0, padding:0, listStyle:"none"}}>
            {m.inputs.map(i => (
              <li key={i} style={{padding:"7px 0", borderBottom:`1px solid ${C.border}`, fontSize:12, color:C.ink2, display:"flex", alignItems:"center", gap:8}}>
                <Upload size={11} color={C.ink3}/> {i}
              </li>
            ))}
          </ul>
        </Card>
        <Card title="Outputs" accent={m.color}>
          <ul style={{margin:0, padding:0, listStyle:"none"}}>
            {m.outputs.map(o => (
              <li key={o} style={{padding:"7px 0", borderBottom:`1px solid ${C.border}`, fontSize:12, color:C.ink2, display:"flex", alignItems:"center", gap:8}}>
                <ArrowRight size={11} color={C.ink3}/> {o}
              </li>
            ))}
          </ul>
        </Card>
        <Card title="Journal posts to CoA" accent={m.color}>
          <ul style={{margin:0, padding:0, listStyle:"none"}}>
            {m.posts.map(p => (
              <li key={p} style={{padding:"7px 0", borderBottom:`1px solid ${C.border}`, fontSize:12, color:C.ink2, display:"flex", alignItems:"center", gap:8, fontFamily:"'JetBrains Mono', monospace"}}>
                {p.startsWith("Dr") ? <ArrowDown size={11} color={C.green}/> : <ArrowUp size={11} color={C.red}/>}
                {p}
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card title="Key controls firing in this module" subtitle={`Tagged to SOX, COSO, ISO 27001, IFRS`} accent={m.color}>
        <div style={{display:"grid", gridTemplateColumns:"repeat(auto-fill, minmax(280px, 1fr))", gap:10}}>
          {m.keyControls.map(c => (
            <div key={c} style={{
              padding:"10px 12px", border:`1px solid ${C.border}`, borderRadius:6,
              background:C.panel2, fontSize:12, color:C.ink2,
              display:"flex", alignItems:"center", gap:10,
            }}>
              <Shield size={14} color={m.color}/>
              <span style={{fontFamily:"'JetBrains Mono', monospace", color:m.color, fontWeight:600, fontSize:11}}>{c.split(" ")[0]}</span>
              <span>{c.split(" ").slice(1).join(" ")}</span>
            </div>
          ))}
        </div>
      </Card>

      <div style={{marginTop:16}}>
        <Card title="AI agents active in this module" accent={m.color}>
          <div style={{display:"grid", gridTemplateColumns:"repeat(auto-fill, minmax(260px, 1fr))", gap:10}}>
            {aiAgents.filter(a => a.modules.includes(m.id)).map(a => (
              <div key={a.id} style={{
                padding:12, border:`1px solid ${C.border}`, borderRadius:6, background:C.panel2,
              }}>
                <div style={{display:"flex", alignItems:"center", gap:8, marginBottom:6}}>
                  <a.icon size={14} color={C.brand2}/>
                  <span style={{fontSize:12, fontWeight:600, color:C.ink}}>{a.name}</span>
                </div>
                <p style={{margin:0, fontSize:11, color:C.ink3, lineHeight:1.45}}>{a.desc}</p>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

// =====================================================================
// VIEW: AI Agents
// =====================================================================
function AgentsView() {
  const [selectedAgent, setSelectedAgent] = useState(aiAgents[0].id);
  const a = aiAgents.find(x => x.id === selectedAgent);

  return (
    <div style={{padding:"28px 28px 60px"}}>
      <div style={{marginBottom:24}}>
        <div style={{fontSize:11, color:C.brand, fontFamily:"'JetBrains Mono', monospace", letterSpacing:"0.2em", marginBottom:10}}>
          AGENT LAYER · 12 AGENTS · CROSS-MODULE
        </div>
        <h1 style={{margin:"0 0 8px", fontSize:32, fontFamily:"'IBM Plex Serif', Georgia, serif", fontWeight:500, color:C.ink, letterSpacing:"-0.02em"}}>The AI agent layer</h1>
        <p style={{margin:0, fontSize:14, color:C.ink2, maxWidth:760, lineHeight:1.55}}>
          Twelve specialist agents co-operate across modules. Each writes to a shared event-bus
          so an action by one (e.g. extraction confidence below threshold) becomes input to
          others (gap-detect raises a prompt, controls-agent escalates).
        </p>
      </div>

      <div style={{display:"grid", gridTemplateColumns:"320px 1fr", gap:16}}>
        <div style={{background:C.panel, border:`1px solid ${C.border}`, borderRadius:10, padding:6, height:"fit-content"}}>
          {aiAgents.map(ag => (
            <button key={ag.id} onClick={()=>setSelectedAgent(ag.id)} style={{
              width:"100%", textAlign:"left", padding:"10px 12px", border:"none",
              background: selectedAgent===ag.id ? `${C.brand}15` : "transparent",
              borderLeft: selectedAgent===ag.id ? `2px solid ${C.brand}` : "2px solid transparent",
              borderRadius:4, cursor:"pointer", color:"inherit",
              display:"flex", alignItems:"center", gap:10, marginBottom:2,
              transition:"all 120ms",
            }}>
              <ag.icon size={14} color={selectedAgent===ag.id ? C.brand : C.ink3}/>
              <div style={{flex:1}}>
                <div style={{fontSize:12, fontWeight:600, color: selectedAgent===ag.id ? C.ink : C.ink2}}>{ag.name}</div>
                <div style={{fontSize:10, color:C.ink3, fontFamily:"'JetBrains Mono', monospace", marginTop:2}}>{ag.modules.join(" · ")}</div>
              </div>
            </button>
          ))}
        </div>

        <div>
          <Card title={a.name} subtitle={`Active in: ${a.modules.join(", ")}`}>
            <p style={{margin:"0 0 16px", fontSize:14, color:C.ink2, lineHeight:1.55}}>{a.desc}</p>

            <div style={{borderTop:`1px solid ${C.border}`, paddingTop:14, marginTop:6}}>
              <div style={{fontSize:11, color:C.ink3, fontFamily:"'JetBrains Mono', monospace", marginBottom:10, letterSpacing:"0.1em"}}>BEHAVIOURAL CONTRACT</div>
              {agentContract(a.id).map((c,i)=>(
                <div key={i} style={{display:"flex", gap:10, alignItems:"flex-start", padding:"6px 0"}}>
                  <span style={{fontSize:10, fontFamily:"'JetBrains Mono', monospace", color:C.brand, marginTop:3, minWidth:24}}>{String(i+1).padStart(2,"0")}</span>
                  <span style={{fontSize:12, color:C.ink2, lineHeight:1.5}}>{c}</span>
                </div>
              ))}
            </div>

            <div style={{borderTop:`1px solid ${C.border}`, paddingTop:14, marginTop:14}}>
              <div style={{fontSize:11, color:C.ink3, fontFamily:"'JetBrains Mono', monospace", marginBottom:10, letterSpacing:"0.1em"}}>HUMAN-IN-THE-LOOP</div>
              <p style={{margin:0, fontSize:12, color:C.ink2, lineHeight:1.55}}>{agentHITL(a.id)}</p>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

function agentContract(id){
  const map = {
    "agt-extract": [
      "Receives raw document (PDF, image, EDI, UBL, JSON).",
      "Emits canonical fields with per-field confidence (0–1) and bounding-box / XPath provenance.",
      "Confidence < 0.85 → field flagged for human confirmation; never silently asserted.",
    ],
    "agt-resolve": [
      "Resolves customer / vendor / item / GL / dimension to master IDs.",
      "Deterministic match first (tax-ID, exact name); fuzzy fallback with similarity score.",
      "Score < 0.85 → returns top-3 candidates, prompts user to pick or create.",
    ],
    "agt-gap": [
      "Compares populated fields against the $1B-company completeness rule-set per cycle.",
      "Returns missing fields with reason (why a $1B co would have it) and severity.",
      "User must (a) provide value, (b) waive with documented reason for audit trail, or (c) escalate.",
    ],
    "agt-anomaly": [
      "Detects: duplicate invoice (exact + fuzzy), BEC bank-change pattern, ghost vendor, PR/PO splitting, round-amount anomaly, weekend posting, dormant-then-active vendor.",
      "Severity-rates the alert; blocks at 'critical', warns at 'high', logs at 'medium'.",
      "All alerts attached to the transaction's audit trail.",
    ],
    "agt-match": [
      "Performs 3-way (PO+GRN+Inv) or 4-way (+ inspection) match at line level.",
      "Tolerances per company × commodity × value-band; learns from historical accepted variances.",
      "Match exceptions blocked with code (Q/P/R/V/T); release requires releaser ≠ poster.",
    ],
    "agt-approver": [
      "Predicts next approver based on DOA matrix, history, and out-of-office rules.",
      "Routes parallel or sequential; escalates on SLA breach.",
      "Logs the predicted-vs-actual to refine the model; never bypasses the DOA.",
    ],
    "agt-tax": [
      "Determines GST/VAT/RCM/WHT per line from item, vendor reg, place of supply, INCOTERMS.",
      "Submits to e-invoice clearance (IRP/SDI/ZATCA/KSeF/PEPPOL) before dispatch.",
      "Versioned tax-rule library; every transaction pinned to a rule version.",
    ],
    "agt-cashapp": [
      "Matches receipts to open invoices using payee, amount, reference, ML-fuzzy.",
      "≥ 95% straight-through target; sub-threshold reviewed by AR clerk (clerk ≠ poster).",
      "Posts FX gain/loss using daily ECB/RBI rate.",
    ],
    "agt-ecl": [
      "Runs IFRS 9 simplified-approach ECL using customer × geography × ageing matrix.",
      "Uses predicted-payment-date (ML) as override input for forward-looking adjustment.",
      "Matrix changes are version-pinned; controller approval required.",
    ],
    "agt-collect": [
      "Predicts late payment 30 days ahead; sequences dunning at the right channel.",
      "Drafts customer outreach in the customer's preferred language and tone.",
      "Suppresses dunning on disputed items; escalates to legal per DOA.",
    ],
    "agt-paymentopt": [
      "Selects payment method per amount × currency × country: RTGS / NEFT / ACH / SEPA / V-card.",
      "Optimises early-pay discount capture vs cost of capital.",
      "Currency-netting and FX hedge alignment with treasury.",
    ],
    "agt-controls": [
      "At posting time: runs SoD, period-open, balance, sanctions, threshold checks.",
      "Blocks any transaction failing a preventive control; logs rationale on detective.",
      "Continuously evaluates SoD ruleset on role-changes; alerts owner on conflict.",
    ],
  };
  return map[id] || ["Behaviour pending."];
}
function agentHITL(id){
  const map = {
    "agt-extract": "Whenever any line is below 0.85 confidence, the user reviews the extracted value side-by-side with the document image (bounding box highlighted). Confirmation event is logged.",
    "agt-resolve": "When a master-data candidate falls below similarity threshold, the user is shown the top-3 matches and chooses or creates. Choice is fed back into the resolver.",
    "agt-gap": "User can provide the missing value, waive (with documented reason → audit trail) or escalate to controller. Waivers above materiality always require dual approval.",
    "agt-anomaly": "Critical alerts always require human acknowledgement; high alerts require ack within 24h or auto-escalate. Mediums are logged for the controls-agent's monthly review.",
    "agt-match": "Blocked invoices route to the buyer/procurement reviewer; release requires reason code and releaser ≠ poster (SoD).",
    "agt-approver": "If predicted approver is out-of-office, substitute is auto-suggested but the substitution event is logged. User sees the predicted chain before submission.",
    "agt-tax": "Manual override of tax determination is gated to the tax-controller role; every override is logged with reason and reviewed quarterly.",
    "agt-cashapp": "Sub-95% confidence matches go to the AR clerk's queue; clerk applies and a different role posts (SoD).",
    "agt-ecl": "Matrix changes are presented to the controller with the impact preview before approval. The user signs off on each version.",
    "agt-collect": "Drafted outreach is presented for review; user can edit voice/tone or send as-is. Customer responses feed back into the model.",
    "agt-paymentopt": "Method routing is automatic, but treasury can lock specific corridors (e.g. payment-rail outage). Discount-capture decisions surface to controller above threshold.",
    "agt-controls": "Preventive failures always block; the user is shown which control fired and what evidence is missing. Detective findings are queued for the controller's daily review.",
  };
  return map[id] || "—";
}

// =====================================================================
// VIEW: Controls
// =====================================================================
function ControlsView(){
  const [filter, setFilter] = useState("all");
  const controls = useMemo(()=> [...controlsData].filter(c =>
    filter === "all" ? true :
    filter === "ar" ? c.id.startsWith("AR") :
    filter === "ap" ? c.id.startsWith("AP") :
    c.id.startsWith("ITGC")
  ), [filter]);

  return (
    <div style={{padding:"28px 28px 60px"}}>
      <div style={{marginBottom:20}}>
        <div style={{fontSize:11, color:C.brand, fontFamily:"'JetBrains Mono', monospace", letterSpacing:"0.2em", marginBottom:10}}>
          CONTROLS REGISTER · 100 CONTROLS · ALL FRAMEWORKS TAGGED
        </div>
        <h1 style={{margin:"0 0 8px", fontSize:32, fontFamily:"'IBM Plex Serif', Georgia, serif", fontWeight:500, color:C.ink, letterSpacing:"-0.02em"}}>Controls in action</h1>
        <p style={{margin:0, fontSize:14, color:C.ink2, maxWidth:760, lineHeight:1.55}}>
          Every transaction triggers a deterministic control sequence. Preventive controls block;
          detective controls log; the audit-trail captures the evidence each time.
        </p>
      </div>

      <div style={{display:"flex", gap:6, marginBottom:14}}>
        {[
          {id:"all", label:"All controls", n:controlsData.length},
          {id:"ar", label:"AR (M1+M2)", n:controlsData.filter(c=>c.id.startsWith("AR")).length},
          {id:"ap", label:"AP (M3+M4)", n:controlsData.filter(c=>c.id.startsWith("AP")).length},
          {id:"itgc", label:"ITGC", n:controlsData.filter(c=>c.id.startsWith("ITGC")).length},
        ].map(b => (
          <button key={b.id} onClick={()=>setFilter(b.id)} style={{
            padding:"8px 14px", borderRadius:6, border:`1px solid ${filter===b.id ? C.brand : C.border}`,
            background: filter===b.id ? `${C.brand}15` : C.panel,
            color: filter===b.id ? C.brand : C.ink2, cursor:"pointer",
            fontSize:12, fontWeight:500, fontFamily:"'JetBrains Mono', monospace",
          }}>
            {b.label} · {b.n}
          </button>
        ))}
      </div>

      <div style={{background:C.panel, border:`1px solid ${C.border}`, borderRadius:10, overflow:"hidden"}}>
        <div style={{
          display:"grid", gridTemplateColumns:"100px 130px 1fr 90px 90px 100px 100px",
          padding:"12px 16px", background:C.panel2, borderBottom:`1px solid ${C.border}`,
          fontSize:10, fontFamily:"'JetBrains Mono', monospace", color:C.ink3, letterSpacing:"0.1em",
        }}>
          <div>ID</div><div>SUB-PROCESS</div><div>DESCRIPTION</div><div>TYPE</div><div>FREQ</div><div>FRAMEWORK</div><div>ASSERTION</div>
        </div>
        <div style={{maxHeight:560, overflow:"auto"}}>
          {controls.map((c,i) => (
            <div key={c.id} style={{
              display:"grid", gridTemplateColumns:"100px 130px 1fr 90px 90px 100px 100px",
              padding:"10px 16px", borderBottom:`1px solid ${C.border}`,
              background: i%2 ? C.panel2 : C.panel, fontSize:11, color:C.ink2, alignItems:"center",
            }}>
              <div style={{fontFamily:"'JetBrains Mono', monospace", color: c.id.startsWith("AR") ? C.brand : c.id.startsWith("AP") ? C.violet : C.blue, fontWeight:600}}>{c.id}</div>
              <div style={{fontSize:10}}>{c.sub}</div>
              <div style={{lineHeight:1.45}}>{c.desc}</div>
              <div><Pill color={c.type === "P" ? C.red : c.type === "D" ? C.amber : C.green}>{c.type}</Pill></div>
              <div style={{fontSize:10, color:C.ink3}}>{c.freq}</div>
              <div style={{fontSize:9, fontFamily:"'JetBrains Mono', monospace", color:C.ink3}}>{c.fw}</div>
              <div style={{fontSize:9, fontFamily:"'JetBrains Mono', monospace", color:C.ink3}}>{c.assert}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const controlsData = [
  // AR (representative top 12 of 35)
  { id:"AR-C01", sub:"Customer master", desc:"KYC + sanctions screen + credit-bureau pull required before customer activation; auto-block until 3 evidence files present.", type:"P", freq:"Per event", fw:"SOX/COSO", assert:"E/O, R&O" },
  { id:"AR-C02", sub:"Customer master", desc:"Bank/remit-to changes require dual approval and 24-hour cool-off before applied to receipts.", type:"P", freq:"Per event", fw:"SOX", assert:"A/V, R&O" },
  { id:"AR-C04", sub:"Order entry", desc:"Credit-limit and AR-block check on every SO release; over-limit requires AR-controller approval.", type:"P", freq:"Per event", fw:"SOX", assert:"R&O, A/V" },
  { id:"AR-C06", sub:"Billing", desc:"Daily exception report: delivery without invoice > 5 days; controller actioned (revenue cut-off).", type:"D", freq:"Daily", fw:"SOX/IFRS15", assert:"C, CO" },
  { id:"AR-C08", sub:"Billing", desc:"Performance-obligation rule applied per IFRS 15; engine version pinned to invoice.", type:"P", freq:"Per event", fw:"IFRS15", assert:"CO, A/V" },
  { id:"AR-C09", sub:"Tax", desc:"Tax-code determination is system-driven; manual override blocked except by tax-controller.", type:"P", freq:"Per event", fw:"SOX", assert:"A/V, P&D" },
  { id:"AR-C10", sub:"E-invoicing", desc:"Submission to IRP/SDI/ZATCA before customer dispatch; un-cleared invoices cannot be sent.", type:"P", freq:"Per event", fw:"Stat", assert:"P&D" },
  { id:"AR-C12", sub:"Posting", desc:"Σ Dr = Σ Cr enforced; no manual journal allowed in AR sub-ledger.", type:"P", freq:"Per event", fw:"SOX", assert:"A/V, C" },
  { id:"AR-C14", sub:"Cash app", desc:"Auto-match threshold 95%; sub-threshold reviewed by AR clerk; clerk ≠ poster.", type:"D", freq:"Daily", fw:"SOX", assert:"E/O, A/V" },
  { id:"AR-C17", sub:"Sub-ledger", desc:"Daily AR sub-ledger to GL recon; difference > tolerance auto-routed to controller.", type:"D", freq:"Daily", fw:"SOX", assert:"C, A/V" },
  { id:"AR-C21", sub:"Write-off", desc:"Write-off > materiality requires CFO + Audit-Committee minute reference attached.", type:"P", freq:"Per event", fw:"SOX/IFRS9", assert:"A/V" },
  { id:"AR-C22", sub:"ECL", desc:"Matrix change requires controller approval; matrix version pinned to each ECL run.", type:"P", freq:"Per change", fw:"IFRS9", assert:"A/V, P&D" },
  // AP (representative top 14 of 45)
  { id:"AP-C01", sub:"Vendor master", desc:"KYC + sanctions + bank-account proof + beneficial-ownership form mandatory before activation.", type:"P", freq:"Per event", fw:"SOX/AML", assert:"E/O, R&O" },
  { id:"AP-C02", sub:"Vendor master", desc:"Bank-change requires dual approval, callback to known number, 24-hour cool-off (anti-BEC).", type:"P", freq:"Per event", fw:"SOX/AML", assert:"E/O, A/V" },
  { id:"AP-C06", sub:"PR", desc:"PR > threshold requires DOA approval; budget-availability check enforced.", type:"P", freq:"Per event", fw:"SOX", assert:"R&O, A/V" },
  { id:"AP-C11", sub:"Receipt", desc:"GRN posted only by warehouse role; SoD prevents requestor = receiver.", type:"P", freq:"Per event", fw:"SOX", assert:"E/O, C" },
  { id:"AP-C14", sub:"Invoice capture", desc:"Block on exact (vendor, ext_no, date, amount); warn on fuzzy duplicate.", type:"P", freq:"Per event", fw:"SOX", assert:"E/O, A/V" },
  { id:"AP-C17", sub:"Match", desc:"3-way match enforced at line; release of blocked invoice requires releaser ≠ poster.", type:"P", freq:"Per event", fw:"SOX", assert:"A/V, E/O" },
  { id:"AP-C20", sub:"Approval", desc:"DOA-driven approval; no auto-approval; out-of-office substitution logged.", type:"P", freq:"Per event", fw:"SOX", assert:"A/V, R&O" },
  { id:"AP-C22", sub:"Tax", desc:"Input-tax determined from item-master + vendor reg; manual override controller-only.", type:"P", freq:"Per event", fw:"SOX", assert:"A/V, P&D" },
  { id:"AP-C24", sub:"WHT", desc:"WHT engine applies section/code; certificate generated; quarterly return reconciled.", type:"P", freq:"Per event", fw:"SOX", assert:"A/V, P&D" },
  { id:"AP-C26", sub:"Posting", desc:"Σ Dr = Σ Cr enforced; period-open check; poster ≠ payer.", type:"P", freq:"Per event", fw:"SOX", assert:"A/V, C" },
  { id:"AP-C29", sub:"Payment", desc:"Dual-control release of bank file; file hash + signing certificates rotated quarterly.", type:"P", freq:"Per run", fw:"SOX/ISO", assert:"E/O, A/V" },
  { id:"AP-C30", sub:"Payment", desc:"Pre-release dup-check (vendor, invoice, amount, period).", type:"P", freq:"Per run", fw:"SOX", assert:"E/O, A/V" },
  { id:"AP-C40", sub:"GR/IR", desc:"GR/IR > 90-day reviewed; written off or accrued with reason.", type:"D", freq:"Monthly", fw:"SOX/IFRS", assert:"C, CO" },
  { id:"AP-C41", sub:"Accruals", desc:"Auto-reversing accrual run for un-invoiced GRNs and SES at period end.", type:"P", freq:"Monthly", fw:"SOX/IFRS", assert:"C, CO" },
  // ITGC (representative)
  { id:"ITGC-01", sub:"Access", desc:"JML workflow integrated with HRIS; no manual user creation.", type:"P", freq:"Per event", fw:"ISO27001", assert:"—" },
  { id:"ITGC-02", sub:"Access", desc:"Quarterly user-access review with risk-rated roles; sign-off retained.", type:"D", freq:"Quarterly", fw:"SOX/ISO", assert:"—" },
  { id:"ITGC-04", sub:"Change mgmt", desc:"All changes via ticketed CR; segregation between developer and deployer.", type:"P", freq:"Per event", fw:"SOX/ISO", assert:"—" },
  { id:"ITGC-13", sub:"SoD", desc:"SoD ruleset enforced at workflow engine; conflicts auto-detected on role change.", type:"P", freq:"Continuous", fw:"SOX/COSO", assert:"—" },
  { id:"ITGC-14", sub:"Audit trail", desc:"Append-only log; tamper-detection via hash-chain; retained 8 years.", type:"P", freq:"Continuous", fw:"SOX/ISO", assert:"—" },
];

// =====================================================================
// VIEW: End-to-end flow (the headline interactive)
// Document → Extract → Gap → Resolve → Match → Controls → JE → ERP
// =====================================================================
function FlowView(){
  const [step, setStep] = useState(0);
  const [waivers, setWaivers] = useState({});

  const steps = [
    {key:"upload",   label:"01 · Document",     icon:Upload},
    {key:"extract",  label:"02 · Extract",      icon:FileCheck},
    {key:"gap",      label:"03 · Gap-engine",   icon:Search},
    {key:"resolve",  label:"04 · Master-data",  icon:Database},
    {key:"match",    label:"05 · 3-way Match",  icon:GitBranch},
    {key:"controls", label:"06 · Controls",     icon:Shield},
    {key:"journal",  label:"07 · Journal",      icon:BookOpen},
    {key:"erp",      label:"08 · ERP Post",     icon:Send},
  ];

  // Compute intermediate values
  const lineCalcs = apDocument.lines.map(l => {
    const qtyVar = (l.invQty - l.grnQty) / l.grnQty;
    const priceVar = (l.invPrice - l.poPrice) / l.poPrice;
    const blocked = Math.abs(qtyVar) > 0.05 ? "Q" : Math.abs(priceVar) > 0.02 ? "P" : "";
    const lineNet = l.invQty * l.invPrice; // before discount, gross = pretax*qty
    return {...l, qtyVar, priceVar, blocked, lineNet};
  });
  // For this demo, accepted goods amounts = grnQty * grnPrice (use poPrice as accepted price after release)
  const acceptedNet = lineCalcs.reduce((s,l) => s + l.grnQty * l.poPrice, 0);
  const taxAmt = acceptedNet * 0.18;
  const gross = acceptedNet + taxAmt;

  const apGaps = useMemo(()=> {
    // Known mappings of doc → fields presence
    const present = {
      vendor:true, vendorBank:true, invoiceNo:true, invoiceDate:true, dueDate:false, // missing
      poRef:true, grnRef:true, currency:true,
      costCentre:false, profitCentre:true, segment:false, project:false,
      taxCode:true, whtCode:false, hsnSac:false,
      contractRef:false, beneficialOwner:false, countryOfOrigin:false,
      icPartner:true, transferPricing:true,
    };
    return billionDollarFields.ap.map(f => ({...f, present: present[f.id]}));
  }, []);

  const missing = apGaps.filter(g => !g.present);
  const missingCritical = missing.filter(g => g.critical);
  const allResolved = missing.every(g => waivers[g.id] || g.present);

  return (
    <div style={{padding:"28px 28px 60px"}}>
      <div style={{marginBottom:20}}>
        <div style={{fontSize:11, color:C.brand, fontFamily:"'JetBrains Mono', monospace", letterSpacing:"0.2em", marginBottom:10}}>
          END-TO-END FLOW · ONE TRANSACTION · 8 STEPS
        </div>
        <h1 style={{margin:"0 0 8px", fontSize:32, fontFamily:"'IBM Plex Serif', Georgia, serif", fontWeight:500, color:C.ink, letterSpacing:"-0.02em"}}>Document <span style={{color:C.brand, fontStyle:"italic"}}>STELLAR_INV_7791.pdf</span> → ERP</h1>
        <p style={{margin:0, fontSize:14, color:C.ink2, maxWidth:780, lineHeight:1.55}}>
          A vendor invoice arrives. Watch how every agent and control fires in sequence to compile
          a balanced journal and post it to SAP S/4HANA.
        </p>
      </div>

      {/* Stepper */}
      <div style={{display:"flex", alignItems:"center", marginBottom:24, padding:"14px 16px", background:C.panel, border:`1px solid ${C.border}`, borderRadius:10, gap:6, overflow:"auto"}}>
        {steps.map((s,i) => (
          <React.Fragment key={s.key}>
            <button onClick={()=>setStep(i)} style={{
              display:"flex", alignItems:"center", gap:8, padding:"6px 12px",
              border:"none", borderRadius:6, cursor:"pointer", flexShrink:0,
              background: i === step ? `${C.brand}1A` : "transparent",
              color: i === step ? C.brand : i < step ? C.green : C.ink3,
              fontSize:11, fontFamily:"'JetBrains Mono', monospace", fontWeight:600, letterSpacing:"0.05em",
            }}>
              <s.icon size={13}/>
              {s.label}
            </button>
            {i < steps.length-1 && <ChevronRight size={12} color={C.ink3} style={{flexShrink:0}}/>}
          </React.Fragment>
        ))}
      </div>

      {/* Step content */}
      {step === 0 && <StepDoc/>}
      {step === 1 && <StepExtract/>}
      {step === 2 && <StepGap gaps={apGaps} waivers={waivers} setWaivers={setWaivers} allResolved={allResolved} missingCritical={missingCritical}/>}
      {step === 3 && <StepResolve/>}
      {step === 4 && <StepMatch lines={lineCalcs}/>}
      {step === 5 && <StepControls/>}
      {step === 6 && <StepJournal acceptedNet={acceptedNet} taxAmt={taxAmt} gross={gross} lineCalcs={lineCalcs}/>}
      {step === 7 && <StepErp gross={gross}/>}

      <div style={{display:"flex", justifyContent:"space-between", marginTop:20}}>
        <button onClick={()=>setStep(Math.max(0, step-1))} disabled={step===0}
          style={btnSecondary(step===0)}>← Previous</button>
        <button onClick={()=>setStep(Math.min(steps.length-1, step+1))} disabled={step===steps.length-1}
          style={btnPrimary(step===steps.length-1)}>
          Next step <ChevronRight size={14} style={{marginLeft:4, verticalAlign:"middle"}}/>
        </button>
      </div>
    </div>
  );
}

const btnPrimary = disabled => ({
  padding:"10px 18px", border:"none", borderRadius:6,
  background: disabled ? `${C.brand}33` : C.brand, color: disabled ? C.ink3 : C.navy,
  fontWeight:600, fontSize:12, fontFamily:"'JetBrains Mono', monospace",
  cursor: disabled ? "not-allowed" : "pointer", letterSpacing:"0.05em",
});
const btnSecondary = disabled => ({
  padding:"10px 18px", border:`1px solid ${C.border}`, borderRadius:6,
  background: "transparent", color: disabled ? C.ink3 : C.ink2,
  fontSize:12, fontFamily:"'JetBrains Mono', monospace",
  cursor: disabled ? "not-allowed" : "pointer", letterSpacing:"0.05em",
});

// ---- Step 1: Document ----
function StepDoc(){
  return (
    <Card title="Step 01 · Document captured" subtitle="Vendor invoice received via email-in channel; SHA-256 hashed and stored in evidence vault" accent={C.brand}>
      <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:20}}>
        <div style={{
          background: C.panel2, border:`1px solid ${C.border}`, borderRadius:8, padding:18, minHeight:320,
          fontFamily:"'IBM Plex Serif', Georgia, serif", fontSize:11, color:C.ink2, lineHeight:1.55,
        }}>
          <div style={{display:"flex", alignItems:"center", justifyContent:"space-between", paddingBottom:8, borderBottom:`1px solid ${C.borderL}`, marginBottom:12}}>
            <div>
              <div style={{fontSize:14, fontWeight:700, color:C.ink}}>STELLAR COMPONENTS LTD</div>
              <div style={{fontSize:10, color:C.ink3}}>Plot 14, Industrial Estate, Pune 411001</div>
              <div style={{fontSize:10, color:C.ink3}}>GSTIN: 07AABCS9876B1Z9</div>
            </div>
            <div style={{textAlign:"right"}}>
              <div style={{fontSize:10, color:C.ink3}}>TAX INVOICE</div>
              <div style={{fontSize:13, color:C.brand, fontWeight:700, fontFamily:"'JetBrains Mono', monospace"}}>STL-INV-7791</div>
              <div style={{fontSize:10, color:C.ink3}}>Date: 22-Apr-2026</div>
            </div>
          </div>
          <div style={{marginBottom:8}}><span style={{color:C.ink3}}>Bill to:</span> Acme Industries Pvt Ltd</div>
          <div style={{marginBottom:12}}><span style={{color:C.ink3}}>PO Ref:</span> PO-2026-1184 &nbsp; <span style={{color:C.ink3}}>GRN Ref:</span> GRN-2026-2204</div>
          <div style={{borderTop:`1px solid ${C.borderL}`, paddingTop:8}}>
            <div style={{display:"grid", gridTemplateColumns:"3fr 1fr 1fr 1fr", gap:8, fontSize:10, color:C.ink3, fontFamily:"'JetBrains Mono', monospace", paddingBottom:6, borderBottom:`1px solid ${C.borderL}`}}>
              <div>ITEM</div><div style={{textAlign:"right"}}>QTY</div><div style={{textAlign:"right"}}>RATE</div><div style={{textAlign:"right"}}>AMOUNT</div>
            </div>
            {apDocument.lines.map(l => (
              <div key={l.ln} style={{display:"grid", gridTemplateColumns:"3fr 1fr 1fr 1fr", gap:8, fontSize:11, padding:"6px 0", borderBottom:`1px dashed ${C.borderL}`}}>
                <div>{l.item}</div>
                <div style={{textAlign:"right"}}>{l.invQty}</div>
                <div style={{textAlign:"right"}}>{fmt(l.invPrice)}</div>
                <div style={{textAlign:"right"}}>{fmt(l.invQty * l.invPrice)}</div>
              </div>
            ))}
          </div>
          <div style={{textAlign:"right", marginTop:12, fontSize:11, fontStyle:"italic", color:C.ink3}}>+ GST 18% applicable</div>
        </div>
        <div>
          <div style={{fontSize:11, color:C.ink3, fontFamily:"'JetBrains Mono', monospace", marginBottom:10, letterSpacing:"0.1em"}}>METADATA</div>
          {[
            ["Channel", "Email-in"],
            ["Filename", "STELLAR_INV_7791.pdf"],
            ["Size", "412 KB"],
            ["SHA-256", "8f4a9c2d…b71e3f08"],
            ["Captured at", "2026-04-25 09:14:23 IST"],
            ["Evidence vault", "ev_01HZ7XK2K0X8MBK..."],
            ["Retention", "8 years (per legal-entity policy)"],
            ["Anti-tamper", "Hash chained · monitored"],
          ].map(([k,v])=>(
            <div key={k} style={{display:"flex", justifyContent:"space-between", padding:"7px 0", borderBottom:`1px solid ${C.border}`}}>
              <span style={{fontSize:11, color:C.ink3}}>{k}</span>
              <span style={{fontSize:11, color:C.ink, fontFamily:k==="SHA-256"||k==="Evidence vault" ? "'JetBrains Mono', monospace":"inherit"}}>{v}</span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

// ---- Step 2: Extract ----
function StepExtract(){
  const fields = [
    {key:"Vendor name",      val:"Stellar Components Ltd", conf:0.99},
    {key:"Vendor GSTIN",     val:"07AABCS9876B1Z9",        conf:0.97},
    {key:"Invoice number",   val:"STL-INV-7791",           conf:0.99},
    {key:"Invoice date",     val:"2026-04-22",             conf:0.95},
    {key:"PO reference",     val:"PO-2026-1184",           conf:0.94},
    {key:"GRN reference",    val:"GRN-2026-2204",          conf:0.91},
    {key:"Currency",         val:"INR",                    conf:0.99},
    {key:"Line 1 — qty",     val:"50",                     conf:0.98},
    {key:"Line 1 — price",   val:"85,000.00",              conf:0.99},
    {key:"Line 2 — qty",     val:"20",                     conf:0.98},
    {key:"Line 2 — price",   val:"18,500.00",              conf:0.99},
    {key:"Line 3 — qty",     val:"10",                     conf:0.92},
    {key:"Line 3 — price",   val:"42,000.00",              conf:0.96},
    {key:"Total (extracted)",val:"6,890,000.00",           conf:0.78}, // low-confidence — gets flagged
  ];
  return (
    <Card title="Step 02 · Extraction Agent" subtitle="OCR + LLM parse against canonical schema · per-field confidence · provenance retained" accent={C.brand}>
      <div style={{display:"grid", gridTemplateColumns:"repeat(2, 1fr)", gap:8}}>
        {fields.map((f,i)=>(
          <div key={i} style={{
            display:"flex", justifyContent:"space-between", alignItems:"center",
            padding:"10px 14px", border:`1px solid ${f.conf < 0.85 ? C.amber : C.border}`,
            background: f.conf < 0.85 ? `${C.amber}10` : C.panel2, borderRadius:6,
          }}>
            <div>
              <div style={{fontSize:10, color:C.ink3, fontFamily:"'JetBrains Mono', monospace", marginBottom:3, letterSpacing:"0.05em"}}>{f.key}</div>
              <div style={{fontSize:13, color:C.ink, fontFamily:"'JetBrains Mono', monospace"}}>{f.val}</div>
            </div>
            <div style={{textAlign:"right"}}>
              <div style={{fontSize:10, color:C.ink3, fontFamily:"'JetBrains Mono', monospace"}}>CONFIDENCE</div>
              <div style={{fontSize:13, fontWeight:700, color: f.conf < 0.85 ? C.amber : C.green, fontFamily:"'JetBrains Mono', monospace"}}>{(f.conf*100).toFixed(0)}%</div>
            </div>
          </div>
        ))}
      </div>
      <div style={{marginTop:14, padding:12, background:`${C.amber}12`, border:`1px solid ${C.amber}55`, borderRadius:6, fontSize:12, color:C.ink2, display:"flex", gap:10, alignItems:"center"}}>
        <AlertTriangle size={16} color={C.amber}/>
        <span>1 field below 0.85 confidence threshold (<b style={{color:C.amber}}>Total — 78%</b>). Will recompute from line items rather than trust the extracted value.</span>
      </div>
    </Card>
  );
}

// ---- Step 3: Gap-engine (the headline) ----
function StepGap({gaps, waivers, setWaivers, allResolved, missingCritical}){
  const present = gaps.filter(g => g.present);
  const missing = gaps.filter(g => !g.present);

  return (
    <>
      <Card title="Step 03 · Gap-Detection Agent" subtitle="A $1B-co invoice has 20 fields. Here are the gaps the agent flagged." accent={C.amber} action={
        <Pill color={missingCritical.length ? C.red : C.green}>
          {missingCritical.length} CRITICAL · {missing.length - missingCritical.length} OPTIONAL · {present.length} OK
        </Pill>
      }>
        <p style={{margin:"0 0 16px", fontSize:12, color:C.ink2, lineHeight:1.55}}>
          The agent compares the populated fields against the completeness rule-set for a USD 1B+
          enterprise. For each gap, it explains why a $1B company would expect the field. Provide a value,
          waive with reason (logged to audit trail), or escalate.
        </p>

        <div style={{marginBottom:14}}>
          <div style={{fontSize:11, color:C.green, fontFamily:"'JetBrains Mono', monospace", letterSpacing:"0.1em", marginBottom:8}}>
            ✓ PRESENT · {present.length}
          </div>
          <div style={{display:"flex", flexWrap:"wrap", gap:6}}>
            {present.map(p => <Pill key={p.id} color={C.green}>{p.label}</Pill>)}
          </div>
        </div>

        <div style={{fontSize:11, color:C.amber, fontFamily:"'JetBrains Mono', monospace", letterSpacing:"0.1em", marginBottom:8, marginTop:18}}>
          ⚠ MISSING · {missing.length} · USER ACTION REQUIRED
        </div>

        <div style={{display:"grid", gap:10}}>
          {missing.map(g => {
            const action = waivers[g.id];
            return (
              <div key={g.id} style={{
                padding:14, border:`1px solid ${g.critical ? `${C.red}55` : C.border}`,
                background: action ? `${C.green}10` : g.critical ? `${C.red}08` : C.panel2,
                borderRadius:6,
              }}>
                <div style={{display:"flex", justifyContent:"space-between", alignItems:"flex-start", gap:14, marginBottom:10}}>
                  <div style={{flex:1}}>
                    <div style={{display:"flex", alignItems:"center", gap:8, marginBottom:4}}>
                      {g.critical
                        ? <Pill color={C.red}>CRITICAL</Pill>
                        : <Pill color={C.amber}>OPTIONAL</Pill>}
                      <span style={{fontSize:13, color:C.ink, fontWeight:600}}>{g.label}</span>
                    </div>
                    <p style={{margin:0, fontSize:11, color:C.ink3, lineHeight:1.5}}>
                      <span style={{color:C.ink2, fontWeight:500}}>Why a $1B co needs it: </span>{g.why}
                    </p>
                  </div>
                  {action && (
                    <Pill color={C.green}>
                      <CheckCircle2 size={11}/>
                      {action === "provided" ? "PROVIDED" : action === "waived" ? "WAIVED" : "ESCALATED"}
                    </Pill>
                  )}
                </div>
                {!action && (
                  <div style={{display:"flex", gap:6}}>
                    <button onClick={()=>setWaivers({...waivers, [g.id]:"provided"})} style={miniBtn(C.brand)}>
                      Provide value
                    </button>
                    <button onClick={()=>setWaivers({...waivers, [g.id]:"waived"})} style={miniBtn(C.amber)}>
                      Waive (with reason)
                    </button>
                    <button onClick={()=>setWaivers({...waivers, [g.id]:"escalated"})} style={miniBtn(C.ink3)}>
                      Escalate
                    </button>
                  </div>
                )}
                {action === "waived" && (
                  <div style={{marginTop:8, padding:8, background:C.panel, border:`1px dashed ${C.borderL}`, borderRadius:4, fontSize:10, color:C.ink3, fontFamily:"'JetBrains Mono', monospace"}}>
                    audit_trail: waiver logged · user_id · ts · reason captured · re-review at next quarter
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div style={{marginTop:18, padding:14, background: allResolved ? `${C.green}10` : `${C.red}08`, border:`1px solid ${allResolved ? C.green : C.red}55`, borderRadius:6, display:"flex", alignItems:"center", gap:12}}>
          {allResolved ? <CheckCircle2 size={18} color={C.green}/> : <AlertOctagon size={18} color={C.red}/>}
          <span style={{fontSize:12, color: allResolved ? C.green : C.red, fontWeight:600}}>
            {allResolved
              ? `All ${missing.length} gaps resolved. Transaction can proceed to master-data resolution.`
              : `${missing.filter(m=>!waivers[m.id]).length} gap(s) still open. Posting blocked until resolved.`}
          </span>
        </div>
      </Card>
    </>
  );
}
const miniBtn = color => ({
  padding:"6px 12px", border:`1px solid ${color}`, borderRadius:4,
  background:"transparent", color, cursor:"pointer",
  fontSize:11, fontFamily:"'JetBrains Mono', monospace", fontWeight:500,
});

// ---- Step 4: Master-data resolve ----
function StepResolve(){
  const items = [
    {field:"Vendor",        extracted:"Stellar Components Ltd",  resolvedTo:"V-44128 · Stellar Components Ltd", method:"Tax-ID exact match (07AABCS9876B1Z9)", score:1.00},
    {field:"PO",            extracted:"PO-2026-1184",            resolvedTo:"PO-2026-1184 · Open · INR 6,500,000", method:"Header lookup — exact",                  score:1.00},
    {field:"GRN",           extracted:"GRN-2026-2204",           resolvedTo:"GRN-2026-2204 · Posted 2026-04-19",  method:"Header lookup — exact",                  score:1.00},
    {field:"Item: Server",  extracted:"Server XR-200",           resolvedTo:"ITM-90041 · Server XR-200",          method:"Item master — exact",                    score:0.99},
    {field:"Item: Storage", extracted:"Storage Disk 4TB",        resolvedTo:"ITM-90158 · Storage Disk 4TB SAS",   method:"Item master — fuzzy",                    score:0.91},
    {field:"Item: Switch",  extracted:"Network Switch 48",       resolvedTo:"ITM-90233 · 48-port Cisco Switch",   method:"Item master — fuzzy",                    score:0.87},
    {field:"Expense GL",    extracted:"—",                       resolvedTo:"510100 · Inventory / RM",            method:"Item-master derivation",                 score:1.00},
    {field:"Cost Centre",   extracted:"—",                       resolvedTo:"C-2200 · IT-Infrastructure",         method:"Requestor's home cost-centre",           score:1.00},
    {field:"Tax Code",      extracted:"GST 18%",                 resolvedTo:"GST-IGST-18 (inter-state)",          method:"Place-of-supply rule",                   score:1.00},
  ];
  return (
    <Card title="Step 04 · Master-Data Resolver" subtitle="Deterministic match first; fuzzy fallback only when needed; nothing is silently asserted" accent={C.blue}>
      <div style={{background:C.panel2, border:`1px solid ${C.border}`, borderRadius:6, overflow:"hidden"}}>
        <div style={{display:"grid", gridTemplateColumns:"180px 1fr 1.2fr 1fr 80px", padding:"10px 14px", borderBottom:`1px solid ${C.border}`,
          fontSize:10, color:C.ink3, fontFamily:"'JetBrains Mono', monospace", letterSpacing:"0.1em"}}>
          <div>FIELD</div><div>EXTRACTED</div><div>RESOLVED TO MASTER</div><div>METHOD</div><div style={{textAlign:"right"}}>SCORE</div>
        </div>
        {items.map((it,i)=>(
          <div key={i} style={{display:"grid", gridTemplateColumns:"180px 1fr 1.2fr 1fr 80px", padding:"10px 14px", borderBottom:`1px solid ${C.border}`, alignItems:"center", fontSize:11, color:C.ink2}}>
            <div style={{color:C.ink3, fontSize:10, fontFamily:"'JetBrains Mono', monospace"}}>{it.field}</div>
            <div style={{fontFamily:"'JetBrains Mono', monospace"}}>{it.extracted}</div>
            <div style={{color:C.ink, fontFamily:"'JetBrains Mono', monospace"}}>{it.resolvedTo}</div>
            <div style={{fontSize:10, color:C.ink3}}>{it.method}</div>
            <div style={{textAlign:"right", fontWeight:700, color: it.score >= 0.95 ? C.green : it.score >= 0.85 ? C.amber : C.red, fontFamily:"'JetBrains Mono', monospace"}}>{(it.score*100).toFixed(0)}%</div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ---- Step 5: Three-way match ----
function StepMatch({lines}){
  const blocks = lines.filter(l => l.blocked);
  return (
    <Card title="Step 05 · Match Agent · 3-way line-level" subtitle="PO + GRN + Invoice; tolerances Q±5%, P±2% — block on breach, never on header-only" accent={C.amber}>
      <div style={{background:C.panel2, border:`1px solid ${C.border}`, borderRadius:6, overflow:"hidden", marginBottom:14}}>
        <div style={{display:"grid", gridTemplateColumns:"40px 1.4fr 60px 60px 60px 90px 90px 80px 80px 110px",
          padding:"10px 14px", borderBottom:`1px solid ${C.border}`,
          fontSize:10, color:C.ink3, fontFamily:"'JetBrains Mono', monospace", letterSpacing:"0.1em"}}>
          <div>LN</div><div>ITEM</div><div>PO</div><div>GRN</div><div>INV</div><div>PO PRICE</div><div>INV PRICE</div><div>QTY VAR</div><div>PRICE VAR</div><div>STATUS</div>
        </div>
        {lines.map(l => {
          const status = l.blocked === "Q" ? "BLOCK · QTY"
                      : l.blocked === "P" ? "BLOCK · PRICE"
                      : "MATCHED";
          const color = l.blocked ? C.red : C.green;
          return (
            <div key={l.ln} style={{display:"grid", gridTemplateColumns:"40px 1.4fr 60px 60px 60px 90px 90px 80px 80px 110px",
              padding:"10px 14px", borderBottom:`1px solid ${C.border}`, alignItems:"center", fontSize:11, color:C.ink2}}>
              <div style={{fontFamily:"'JetBrains Mono', monospace"}}>{l.ln}</div>
              <div style={{color:C.ink}}>{l.item}</div>
              <div style={{fontFamily:"'JetBrains Mono', monospace"}}>{l.poQty}</div>
              <div style={{fontFamily:"'JetBrains Mono', monospace"}}>{l.grnQty}</div>
              <div style={{fontFamily:"'JetBrains Mono', monospace"}}>{l.invQty}</div>
              <div style={{fontFamily:"'JetBrains Mono', monospace"}}>{fmt(l.poPrice)}</div>
              <div style={{fontFamily:"'JetBrains Mono', monospace"}}>{fmt(l.invPrice)}</div>
              <div style={{fontFamily:"'JetBrains Mono', monospace", color: Math.abs(l.qtyVar) > 0.05 ? C.red : C.ink2}}>{(l.qtyVar*100).toFixed(2)}%</div>
              <div style={{fontFamily:"'JetBrains Mono', monospace", color: Math.abs(l.priceVar) > 0.02 ? C.red : C.ink2}}>{(l.priceVar*100).toFixed(2)}%</div>
              <div><Pill color={color}>{status}</Pill></div>
            </div>
          );
        })}
      </div>

      <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:10}}>
        {blocks.map(l => (
          <div key={l.ln} style={{padding:14, border:`1px solid ${C.red}55`, background:`${C.red}08`, borderRadius:6}}>
            <div style={{display:"flex", alignItems:"center", gap:8, marginBottom:8}}>
              <AlertOctagon size={14} color={C.red}/>
              <span style={{fontSize:12, fontWeight:600, color:C.ink}}>Line {l.ln}: {l.item}</span>
            </div>
            <div style={{fontSize:11, color:C.ink2, lineHeight:1.55}}>
              {l.blocked === "Q"
                ? <>Invoice billed {l.invQty}, but only {l.grnQty} received. Variance {((l.qtyVar)*100).toFixed(2)}% exceeds tolerance ±5%. Resolution: <b style={{color:C.amber}}>release for accepted qty only</b> ({l.grnQty} units), recover the difference via short-payment or vendor credit-note.</>
                : <>Invoice price {fmt(l.invPrice)} vs PO price {fmt(l.poPrice)}. Variance {((l.priceVar)*100).toFixed(2)}% exceeds tolerance ±2%. Resolution: <b style={{color:C.amber}}>buyer review required</b>; release at PO price unless contract amendment evidenced.</>}
            </div>
            <div style={{marginTop:8, fontSize:10, color:C.ink3, fontFamily:"'JetBrains Mono', monospace"}}>
              SoD: releaser ≠ poster · approver above creator level · reason code mandatory
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ---- Step 6: Controls ----
function StepControls(){
  const checks = [
    {id:"AP-C14", name:"Duplicate-invoice (exact)",          status:"pass", detail:"Hash unique · vendor+ext_no+date+amt unseen"},
    {id:"AP-C17", name:"Three-way match (line-level)",        status:"warn", detail:"2 line blocks (Q on Ln 3, P on Ln 2) · released at accepted values"},
    {id:"AP-C20", name:"DOA approval chain",                  status:"pass", detail:"Mgr (₹500K) → FinCtrl (₹5M) · within delegation"},
    {id:"AP-C21", name:"SoD: poster ≠ approver",              status:"pass", detail:"u1 (creator) ≠ u2 (FinCtrl approver) · workflow-enforced"},
    {id:"AP-C22", name:"Input-tax determination",             status:"pass", detail:"GST-IGST-18 from PoS=Maharashtra inter-state"},
    {id:"AP-C24", name:"WHT / TDS deduction",                 status:"warn", detail:"Goods purchase, no TDS; user waived sec 194Q (turnover threshold)"},
    {id:"AP-C26", name:"Σ Dr = Σ Cr (balance)",               status:"pass", detail:"Dr 5,848,080.00 = Cr 5,848,080.00"},
    {id:"AP-C27", name:"Period open",                         status:"pass", detail:"Period 2026-04 = OPEN for IN-DEL-01"},
    {id:"AP-C34", name:"Vendor sanctions screen",             status:"pass", detail:"Stellar Components Ltd · OFAC/UN/EU clear"},
    {id:"AP-C45", name:"Evidence linkage",                    status:"pass", detail:"ev_01HZ7XK2K0X8MBK · hash matches"},
  ];
  return (
    <Card title="Step 06 · Controls Agent" subtitle="Posting preconditions — preventive failures block, detective findings log" accent={C.green}>
      <div style={{display:"grid", gap:6}}>
        {checks.map(c => {
          const color = c.status === "pass" ? C.green : c.status === "warn" ? C.amber : C.red;
          const Icon = c.status === "pass" ? CheckCircle2 : c.status === "warn" ? AlertTriangle : XCircle;
          return (
            <div key={c.id} style={{
              display:"grid", gridTemplateColumns:"30px 100px 1fr 1.4fr",
              alignItems:"center", padding:"10px 14px",
              border:`1px solid ${C.border}`, borderRadius:6, background:C.panel2,
            }}>
              <Icon size={16} color={color}/>
              <div style={{fontSize:11, fontFamily:"'JetBrains Mono', monospace", color, fontWeight:600}}>{c.id}</div>
              <div style={{fontSize:12, color:C.ink}}>{c.name}</div>
              <div style={{fontSize:11, color:C.ink3}}>{c.detail}</div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

// ---- Step 7: Journal compile ----
function StepJournal({acceptedNet, taxAmt, gross, lineCalcs}){
  // Build JE rows from accepted values
  const inv = lineCalcs[0]; // Server
  const dsk = lineCalcs[1]; // Storage
  const sw  = lineCalcs[2]; // Switch — blocked, accept GRN qty * PO price
  const lns = [
    { type:"Dr", account:"510100 Inventory / RM",     desc:"Server XR-200 (50 × 85,000)",      amt: 50 * 85000,      cc:"C-2200", pc:"P-IN-01" },
    { type:"Dr", account:"510100 Inventory / RM",     desc:"Storage Disk 4TB (20 × 18,000)",   amt: 20 * 18000,      cc:"C-2200", pc:"P-IN-01" },
    { type:"Dr", account:"510100 Inventory / RM",     desc:"Network Switch (8 × 42,000)",      amt: 8  * 42000,      cc:"C-2200", pc:"P-IN-01" },
    { type:"Dr", account:"240100 Input GST 18%",      desc:"Input IGST 18% on goods",          amt: taxAmt,          cc:"—",      pc:"P-IN-01" },
    { type:"Cr", account:"210100 Trade Payables",     desc:"Vendor payable (gross)",           amt: gross,           cc:"—",      pc:"P-IN-01" },
  ];
  const dr = lns.filter(l => l.type === "Dr").reduce((s,l) => s + l.amt, 0);
  const cr = lns.filter(l => l.type === "Cr").reduce((s,l) => s + l.amt, 0);
  const balanced = Math.abs(dr - cr) < 0.01;

  return (
    <Card title="Step 07 · Journal Entry compiled" subtitle="Posted only after all controls pass · balance enforced · dimensions populated" accent={C.brand}>
      <div style={{background:C.panel2, border:`1px solid ${C.border}`, borderRadius:6, overflow:"hidden"}}>
        <div style={{display:"grid", gridTemplateColumns:"60px 240px 1fr 80px 80px 140px",
          padding:"10px 14px", borderBottom:`1px solid ${C.border}`,
          fontSize:10, color:C.ink3, fontFamily:"'JetBrains Mono', monospace", letterSpacing:"0.1em"}}>
          <div>DR/CR</div><div>GL ACCOUNT</div><div>DESCRIPTION</div><div>CC</div><div>PC</div><div style={{textAlign:"right"}}>AMOUNT</div>
        </div>
        {lns.map((l,i)=>(
          <div key={i} style={{display:"grid", gridTemplateColumns:"60px 240px 1fr 80px 80px 140px",
            padding:"10px 14px", borderBottom:`1px solid ${C.border}`, alignItems:"center", fontSize:11, color:C.ink2}}>
            <div><Pill color={l.type === "Dr" ? C.green : C.red}>{l.type}</Pill></div>
            <div style={{color:C.ink, fontFamily:"'JetBrains Mono', monospace"}}>{l.account}</div>
            <div>{l.desc}</div>
            <div style={{fontFamily:"'JetBrains Mono', monospace", fontSize:10}}>{l.cc}</div>
            <div style={{fontFamily:"'JetBrains Mono', monospace", fontSize:10}}>{l.pc}</div>
            <div style={{textAlign:"right", fontFamily:"'JetBrains Mono', monospace", color:C.ink, fontWeight:600}}>{fmt(l.amt)}</div>
          </div>
        ))}
        <div style={{display:"grid", gridTemplateColumns:"60px 240px 1fr 80px 80px 140px",
          padding:"12px 14px", background:`${C.brand}10`,
          fontSize:11, fontWeight:700, color:C.ink, alignItems:"center"}}>
          <div></div><div></div>
          <div style={{textAlign:"right", fontFamily:"'JetBrains Mono', monospace", fontSize:10, color:C.ink3, letterSpacing:"0.1em"}}>Σ DEBITS · Σ CREDITS · BALANCE</div>
          <div style={{textAlign:"right", fontFamily:"'JetBrains Mono', monospace", color:C.green}}>{fmt(dr)}</div>
          <div style={{textAlign:"right", fontFamily:"'JetBrains Mono', monospace", color:C.red}}>{fmt(cr)}</div>
          <div style={{textAlign:"right", fontFamily:"'JetBrains Mono', monospace", color: balanced ? C.green : C.red}}>
            {balanced ? "✓ BALANCED" : "✗ DIFF"}
          </div>
        </div>
      </div>
      <div style={{marginTop:14, padding:14, background:C.panel2, border:`1px solid ${C.border}`, borderRadius:6, fontSize:11, color:C.ink3, lineHeight:1.6}}>
        <div style={{fontFamily:"'JetBrains Mono', monospace", color:C.brand2, marginBottom:6, letterSpacing:"0.1em", fontSize:10}}>POSTING META</div>
        <div>External ID: <span style={{color:C.ink, fontFamily:"'JetBrains Mono', monospace"}}>FIN-AP-2026-0009824</span> (idempotency key)</div>
        <div>Posting period: <span style={{color:C.ink, fontFamily:"'JetBrains Mono', monospace"}}>2026-04 · OPEN</span></div>
        <div>Doc type: <span style={{color:C.ink, fontFamily:"'JetBrains Mono', monospace"}}>RE · Vendor invoice with PO</span></div>
        <div>Sub-ledger: <span style={{color:C.ink, fontFamily:"'JetBrains Mono', monospace"}}>AP · GR/IR cleared</span></div>
      </div>
    </Card>
  );
}

// ---- Step 8: ERP post ----
function StepErp({gross}){
  const [posted, setPosted] = useState(false);
  const [posting, setPosting] = useState(false);
  return (
    <Card title="Step 08 · Idempotent push to SAP S/4HANA" subtitle="Connector translates canonical payload → BAPI_ACC_DOCUMENT_POST · retry-safe · evidence-linked" accent={C.brand}>
      <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:16}}>
        <div>
          <div style={{fontSize:11, color:C.ink3, fontFamily:"'JetBrains Mono', monospace", letterSpacing:"0.1em", marginBottom:10}}>CANONICAL PAYLOAD</div>
          <pre style={{
            margin:0, padding:14, background:C.panel2, border:`1px solid ${C.border}`, borderRadius:6,
            fontSize:10.5, color:C.ink, fontFamily:"'JetBrains Mono', monospace", lineHeight:1.55, overflow:"auto", maxHeight:340,
          }}>{`{
  "txn_type": "ap.invoice",
  "external_id": "FIN-AP-2026-0009824",
  "le_id": "IN-DEL-01",
  "vendor_id": "V-44128",
  "doc_no": "STL-INV-7791",
  "doc_date": "2026-04-22",
  "post_date": "2026-04-25",
  "currency": "INR",
  "po_ref": "PO-2026-1184",
  "grn_ref": "GRN-2026-2204",
  "lines": [
    {"ln":1,"qty":50,"price":85000.00,"gl":"510100"},
    {"ln":2,"qty":20,"price":18000.00,"gl":"510100"},
    {"ln":3,"qty":8, "price":42000.00,"gl":"510100"}
  ],
  "tax": {"code":"GST-IGST-18","amount":${taxAmtFn(gross).toFixed(2)}},
  "balance": {"dr": ${gross.toFixed(2)}, "cr": ${gross.toFixed(2)}, "ok": true},
  "evidence_id": "ev_01HZ7XK2K0X8MBK..."
}`}</pre>
        </div>
        <div>
          <div style={{fontSize:11, color:C.ink3, fontFamily:"'JetBrains Mono', monospace", letterSpacing:"0.1em", marginBottom:10}}>SAP S/4 BAPI CALL</div>
          <pre style={{
            margin:0, padding:14, background:C.panel2, border:`1px solid ${C.border}`, borderRadius:6,
            fontSize:10.5, color:C.ink, fontFamily:"'JetBrains Mono', monospace", lineHeight:1.55, overflow:"auto", maxHeight:340,
          }}>{`BAPI_ACC_DOCUMENT_POST
  DOCUMENTHEADER
    BUKRS    = 'IN01'
    BLART    = 'RE'
    BLDAT    = '20260422'
    BUDAT    = '20260425'
    XBLNR    = 'STL-INV-7791'
    WAERS    = 'INR'
  ACCOUNTPAYABLE
    LIFNR    = 'V44128'
    PMNTTRMS = 'NT30'
  ACCOUNTGL  (× 4 lines)
    HKONT    = '510100' / '240100'
    KOSTL    = 'C-2200'
    PRCTR    = 'P-IN-01'
  CURRENCYAMOUNT
    WRBTR    = ${gross.toFixed(2)}

→ BELNR / GJAHR returned
→ stored on FIN-AP-2026-0009824`}</pre>
        </div>
      </div>

      <div style={{marginTop:18, display:"flex", justifyContent:"center"}}>
        {!posted ? (
          <button onClick={()=>{
            setPosting(true);
            setTimeout(()=>{ setPosting(false); setPosted(true); }, 1400);
          }} disabled={posting} style={{
            padding:"14px 28px", background: posting ? `${C.brand}66` : C.brand, color:C.navy,
            border:"none", borderRadius:6, cursor:posting?"wait":"pointer", fontWeight:700,
            fontSize:13, fontFamily:"'JetBrains Mono', monospace", letterSpacing:"0.05em",
            display:"inline-flex", alignItems:"center", gap:8,
          }}>
            {posting ? <><Activity size={14} className="spin"/> POSTING TO SAP…</> : <><Send size={14}/> POST TO SAP S/4HANA</>}
          </button>
        ) : (
          <div style={{
            padding:"18px 24px", background:`${C.green}15`, border:`1px solid ${C.green}55`, borderRadius:6,
            display:"flex", alignItems:"center", gap:14,
          }}>
            <CheckCircle2 size={24} color={C.green}/>
            <div>
              <div style={{fontSize:13, fontWeight:600, color:C.green}}>POSTED · SAP doc 5100002847 / FY 2026</div>
              <div style={{fontSize:11, color:C.ink3, fontFamily:"'JetBrains Mono', monospace", marginTop:3}}>
                Sub-ledger updated · GR/IR cleared · Evidence linked · Audit trail closed · TB updated
              </div>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
function taxAmtFn(gross){ return gross * 0.18 / 1.18; }

// =====================================================================
// MAIN APP
// =====================================================================
export default function FinqorPlatform() {
  const [activeModule, setActiveModule] = useState("overview");

  return (
    <div style={{
      minHeight:"100vh", background:C.bg, color:C.ink,
      fontFamily:"'Inter', system-ui, -apple-system, sans-serif",
      fontSize:14, lineHeight:1.5,
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Serif:ital,wght@0,400;0,500;0,600;0,700;1,500&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');
        * { box-sizing: border-box; }
        body { margin: 0; }
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: ${C.bg}; }
        ::-webkit-scrollbar-thumb { background: ${C.border}; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: ${C.borderL}; }
        .spin { animation: spin 1s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
        button:focus { outline: none; }
        button:focus-visible { outline: 2px solid ${C.brand}; outline-offset: 2px; }
      `}</style>
      <Header activeModule={activeModule} setActiveModule={setActiveModule}/>
      <main style={{maxWidth:1340, margin:"0 auto"}}>
        {activeModule === "overview" && <OverviewView setActiveModule={setActiveModule}/>}
        {["M1","M2","M3","M4"].includes(activeModule) && <ModuleView moduleId={activeModule} setActiveModule={setActiveModule}/>}
        {activeModule === "agents" && <AgentsView/>}
        {activeModule === "controls" && <ControlsView/>}
        {activeModule === "flow" && <FlowView/>}
      </main>
      <footer style={{
        borderTop:`1px solid ${C.border}`, padding:"24px 28px",
        marginTop:32, fontSize:11, color:C.ink3, textAlign:"center",
        fontFamily:"'JetBrains Mono', monospace", letterSpacing:"0.05em",
      }}>
        FINQOR · ACCOUNTING LAYER · v1.0 · CONFIDENTIAL · © 2026
      </footer>
    </div>
  );
}
