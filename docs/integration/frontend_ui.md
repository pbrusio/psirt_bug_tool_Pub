# Frontend Integration

## Updated Scanner Form

```tsx
// Unified Scan Options
<div className="scan-options">
  <h3>Scan Against:</h3>
  <label>
    <input type="checkbox" checked={scanBugs} onChange={(e) => setScanBugs(e.target.checked)} />
    Bug Database (9,586 bugs)
  </label>
  <label>
    <input type="checkbox" checked={scanPSIRTs} onChange={(e) => setScanPSIRTs(e.target.checked)} />
    PSIRT Cache (165 advisories)
  </label>

  {/* Default: both checked */}
</div>
```

## Updated Results Display

```tsx
<div className="unified-results">
  <h2>Scan Results</h2>

  <div className="summary">
    <p>Total Vulnerabilities: {result.total_vulnerabilities}</p>
    <p>
      • {result.breakdown.from_bugs} from Bug Database
      • {result.breakdown.from_psirts} from PSIRT Cache
    </p>
  </div>

  <div className="vulnerability-list">
    {result.vulnerabilities.map(vuln => (
      <div key={vuln.id} className={`vuln-card ${vuln.type.toLowerCase()}`}>
        <span className="type-badge">{vuln.type}</span>
        <h4>{vuln.id} - {vuln.title}</h4>
        <p>{vuln.summary}</p>
        <div className="metadata">
          <span>Severity: {getSeverityLabel(vuln.severity)}</span>
          {vuln.cve_ids.length > 0 && (
            <span>CVEs: {vuln.cve_ids.join(', ')}</span>
          )}
          {vuln.type === "PSIRT" && (
            <span>Confidence: {Math.round(vuln.confidence * 100)}%</span>
          )}
        </div>
      </div>
    ))}
  </div>
</div>
```
