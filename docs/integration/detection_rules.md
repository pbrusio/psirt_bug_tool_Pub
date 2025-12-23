# Exploitation Detection Rules (Unified IOC Generation)

## Use Case
"Generate Firepower rules for ALL vulnerabilities (bugs + PSIRTs)"

## Implementation

```python
def generate_detection_rules_unified(
    vulnerabilities: List[UnifiedVulnerability],
    rule_format: str = "firepower"  # "firepower", "stealthwatch", "snort"
) -> List[str]:
    """
    Generate detection rules for a list of unified vulnerabilities.
    Works for both bugs and PSIRTs.
    """

    rules = []

    for vuln in vulnerabilities:
        # Skip vulnerabilities without exploitation intelligence
        if not vuln.exploit_available and not vuln.affected_ports:
            # Generate behavioral rule as fallback
            rule = generate_behavioral_rule(vuln, rule_format)
            rules.append(rule)
            continue

        # Generate signature-based rule if IOCs available
        if vuln.exploit_iocs:
            rule = generate_signature_rule(vuln, rule_format)
            rules.append(rule)

        # Generate port-based rule if affected ports known
        elif vuln.affected_ports:
            rule = generate_port_based_rule(vuln, rule_format)
            rules.append(rule)

    return rules

def generate_signature_rule(vuln: UnifiedVulnerability, format: str) -> str:
    """Generate signature-based detection rule."""

    if format == "firepower":
        return f'''
alert tcp any any -> $AFFECTED_DEVICES {vuln.affected_ports[0]} (
  msg:"[{vuln.type}] {vuln.id} - {vuln.title}";
  flow:to_server,established;
  content:"{vuln.exploit_iocs[0]['pattern']}";
  sid:{generate_sid(vuln.id)}; rev:1;
  reference:url,{vuln.url};
  classtype:attempted-admin;
  priority:{vuln.severity};
)
'''
    elif format == "stealthwatch":
        return json.dumps({
            'name': f'{vuln.type} {vuln.id} Detection',
            'conditions': [
                {'dst': '$AFFECTED_DEVICES', 'port': vuln.affected_ports[0]},
                {'pattern': vuln.exploit_iocs[0]['pattern']}
            ],
            'severity': vuln.severity,
            'reference': vuln.url
        })
```
