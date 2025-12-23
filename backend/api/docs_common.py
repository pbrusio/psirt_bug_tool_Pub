"""
Shared Documentation Styles and Templates
Centralizes the look and feel for all documentation pages.
"""

# Combined CSS styles from all documentation pages
SHARED_STYLES = """
    :root {
        --bg-primary: #0f172a;
        --bg-secondary: #1e293b;
        --bg-card: #334155;
        --text-primary: #f8fafc;
        --text-secondary: #94a3b8;
        --accent-blue: #3b82f6;
        --accent-green: #22c55e;
        --accent-orange: #f97316;
        --accent-purple: #a855f7;
        --accent-red: #ef4444;
        --accent-cyan: #06b6d4;
        --border-color: #475569;
    }

    * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }

    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
        background: var(--bg-primary);
        color: var(--text-primary);
        line-height: 1.6;
    }

    /* Top Navigation Bar */
    .top-nav {
        background: var(--bg-secondary);
        border-bottom: 1px solid var(--border-color);
        padding: 0.75rem 2rem;
        position: sticky;
        top: 0;
        z-index: 100;
        display: flex;
        align-items: center;
        gap: 2rem;
    }

    .nav-brand {
        font-weight: 700;
        font-size: 1.1rem;
        color: var(--text-primary);
        text-decoration: none;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .nav-brand:hover {
        color: var(--accent-blue);
    }

    .nav-links {
        display: flex;
        gap: 0.5rem;
        flex-wrap: wrap;
    }

    .nav-link {
        padding: 0.5rem 1rem;
        border-radius: 6px;
        text-decoration: none;
        font-size: 0.9rem;
        font-weight: 500;
        transition: all 0.2s;
        color: var(--text-secondary);
        background: transparent;
    }

    .nav-link:hover {
        background: var(--bg-card);
        color: var(--text-primary);
    }

    /* Active States */
    .nav-link.active {
        color: white;
        background: var(--bg-card); /* Default active background if specific class not matched */
    }

    /* Specific Active Colors */
    .nav-link.hub.active { background: var(--bg-card); }
    .nav-link.tutorial.active { background: var(--accent-blue); }
    .nav-link.admin.active { background: var(--accent-orange); }
    .nav-link.setup.active { background: var(--accent-green); }
    .nav-link.api.active { background: var(--accent-purple); }
    .nav-link.arch.active { background: var(--accent-cyan); }

    /* Left Borders for visual indicators */
    .nav-link.tutorial { border-left: 3px solid var(--accent-blue); }
    .nav-link.admin { border-left: 3px solid var(--accent-orange); }
    .nav-link.setup { border-left: 3px solid var(--accent-green); }
    .nav-link.api { border-left: 3px solid var(--accent-purple); }
    .nav-link.arch { border-left: 3px solid var(--accent-cyan); }
    
    /* Hover effects for bordered links - match their color */
    .nav-link.tutorial:hover { background: rgba(59, 130, 246, 0.1); color: white; }
    .nav-link.admin:hover { background: rgba(249, 115, 22, 0.1); color: white; }
    .nav-link.setup:hover { background: rgba(34, 197, 94, 0.1); color: white; }
    .nav-link.api:hover { background: rgba(168, 85, 247, 0.1); color: white; }
    .nav-link.arch:hover { background: rgba(6, 182, 212, 0.1); color: white; }


    /* Main content area */
    .main-content {
        padding: 2rem;
        max-width: 1200px;
        margin: 0 auto;
    }

    h1 {
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
        /* Default gradient, can be overridden per page */
        background: linear-gradient(135deg, var(--text-primary), var(--text-secondary));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    /* Page specific H1 gradients */
    .page-hub h1 { background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .page-admin h1 { background: linear-gradient(135deg, var(--accent-orange), var(--accent-red)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .page-tutorial h1 { background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .page-setup h1 { background: linear-gradient(135deg, var(--accent-green), var(--accent-cyan)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }

    .subtitle {
        color: var(--text-secondary);
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }

    h2 {
        margin: 2rem 0 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid var(--border-color);
        color: var(--text-primary);
    }
    
    /* Page specific H2 colors */
    .page-admin h2 { color: var(--accent-orange); }
    .page-tutorial h2 { color: var(--accent-blue); }
    .page-setup h2 { color: var(--accent-green); }

    h3 {
        color: var(--text-primary);
        margin: 1.5rem 0 0.75rem;
    }

    h4 {
        margin: 1rem 0 0.5rem;
        color: var(--text-primary); /* Default */
    }
    .page-admin h4 { color: var(--accent-blue); }
    .page-setup h4 { color: var(--accent-blue); }

    code {
        background: var(--bg-card);
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        font-family: 'Courier New', monospace;
        font-size: 0.9em;
    }

    pre {
        background: var(--bg-primary);
        border-radius: 8px;
        padding: 1rem;
        overflow-x: auto;
        margin: 1rem 0;
        border: 1px solid var(--border-color);
    }

    pre code {
        background: none;
        padding: 0;
    }

    table {
        width: 100%;
        border-collapse: collapse;
        margin: 1rem 0;
    }

    th, td {
        padding: 0.75rem 1rem;
        text-align: left;
        border-bottom: 1px solid var(--border-color);
    }

    th {
        background: var(--bg-card);
        font-weight: 600;
    }

    ul, ol {
        margin: 0.5rem 0 0.5rem 1.5rem;
    }

    li {
        margin: 0.5rem 0;
    }

    /* Common Components */
    
    /* Tip/Info Box */
    .tip {
        background: rgba(59, 130, 246, 0.1);
        border-left: 4px solid var(--accent-blue);
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0 8px 8px 0;
    }

    .tip-label {
        color: var(--accent-blue);
        font-weight: 600;
        font-size: 0.85rem;
        text-transform: uppercase;
        margin-bottom: 0.5rem;
    }

    /* Warning Box */
    .warning {
        background: rgba(239, 68, 68, 0.1);
        border-left: 4px solid var(--accent-red);
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0 8px 8px 0;
    }

    .warning-label {
        color: var(--accent-red);
        font-weight: 600;
        font-size: 0.85rem;
        text-transform: uppercase;
        margin-bottom: 0.5rem;
    }
    
    /* Success Box */
    .success {
        background: rgba(34, 197, 94, 0.1);
        border-left: 4px solid var(--accent-green);
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0 8px 8px 0;
    }

    .success-label {
        color: var(--accent-green);
        font-weight: 600;
        font-size: 0.85rem;
        text-transform: uppercase;
        margin-bottom: 0.5rem;
    }

    /* Command Block */
    .command-block {
        background: var(--bg-primary);
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
        font-family: 'Courier New', monospace;
        font-size: 0.9rem;
        border-left: 3px solid var(--accent-green);
    }

    .command-block .prompt {
        color: var(--accent-green);
    }
    
    .command-block .comment {
        color: var(--text-secondary);
    }
    
    /* Document Cards (Hub) */
    .doc-card {
        background: var(--bg-secondary);
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid var(--border-color);
        text-decoration: none;
        color: var(--text-primary);
        transition: all 0.3s;
        display: block;
    }

    .doc-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
    }

    .doc-card.tutorial { border-top: 4px solid var(--accent-blue); }
    .doc-card.admin { border-top: 4px solid var(--accent-orange); }
    .doc-card.setup { border-top: 4px solid var(--accent-green); }
    .doc-card.api { border-top: 4px solid var(--accent-purple); }
    .doc-card.arch { border-top: 4px solid var(--accent-cyan); }

    .doc-card:hover.tutorial { border-color: var(--accent-blue); }
    .doc-card:hover.admin { border-color: var(--accent-orange); }
    .doc-card:hover.setup { border-color: var(--accent-green); }
    .doc-card:hover.api { border-color: var(--accent-purple); }
    .doc-card:hover.arch { border-color: var(--accent-cyan); }
    
    /* Hub Grid */
    .docs-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: 1.5rem;
        margin: 2rem 0;
    }
    
    .doc-icon { font-size: 2.5rem; margin-bottom: 1rem; }
    .doc-title { font-size: 1.25rem; font-weight: 600; margin-bottom: 0.5rem; }
    .doc-desc { color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 1rem; }
    
    .doc-tags { display: flex; gap: 0.5rem; flex-wrap: wrap; }
    .tag {
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 500;
        background: var(--bg-card);
        color: var(--text-secondary);
    }
    
    /* Status Section (Hub) */
    .status-section {
        background: var(--bg-secondary);
        border-radius: 12px;
        padding: 1.5rem;
        margin: 2rem 0;
        border: 1px solid var(--border-color);
    }

    .status-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 1rem;
        margin-top: 1rem;
    }

    .status-item {
        text-align: center;
        padding: 1rem;
        background: var(--bg-primary);
        border-radius: 8px;
    }

    .status-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: var(--accent-green);
    }

    .status-label {
        font-size: 0.8rem;
        color: var(--text-secondary);
        margin-top: 0.25rem;
    }
    
    /* Quick Links (Hub) */
    .quick-links {
        background: var(--bg-secondary);
        border-radius: 12px;
        padding: 1.5rem;
        margin: 2rem 0;
        border: 1px solid var(--border-color);
    }
    
    .quick-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
    }

    .quick-item {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.75rem 1rem;
        background: var(--bg-primary);
        border-radius: 8px;
        text-decoration: none;
        color: var(--text-primary);
        transition: background 0.2s;
    }

    .quick-item:hover { background: var(--bg-card); }
    .quick-icon { font-size: 1.25rem; }
    .quick-label { font-size: 0.9rem; }
    
    /* Badges */
    .badge {
        display: inline-block;
        padding: 0.15rem 0.5rem;
        border-radius: 9999px;
        font-size: 0.7rem;
        font-weight: 600;
    }
    .badge.external { background: rgba(168, 85, 247, 0.2); color: var(--accent-purple); }
    .badge.processing { background: rgba(249, 115, 22, 0.2); color: var(--accent-orange); }
    .badge.runtime { background: rgba(34, 197, 94, 0.2); color: var(--accent-green); }
    .badge.speed { background: rgba(34, 197, 94, 0.2); color: var(--accent-green); }
    .badge.smart { background: rgba(168, 85, 247, 0.2); color: var(--accent-purple); }

    /* Admin Guide Components */
    .nav-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
        margin: 1.5rem 0 2rem;
    }

    .nav-card {
        background: var(--bg-secondary);
        border-radius: 8px;
        padding: 1rem;
        border: 1px solid var(--border-color);
        text-decoration: none;
        color: var(--text-primary);
        transition: border-color 0.2s, transform 0.2s;
    }

    .nav-card:hover {
        border-color: var(--accent-orange);
        transform: translateY(-2px);
    }
    
    .nav-card .nav-title { font-weight: 600; margin-bottom: 0.25rem; }
    .nav-card .nav-desc { font-size: 0.85rem; color: var(--text-secondary); }

    .data-stack {
        background: var(--bg-secondary);
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1.5rem 0;
        border: 1px solid var(--border-color);
    }

    .stack-layer {
        background: var(--bg-card);
        border-radius: 8px;
        padding: 1rem;
        margin: 0.75rem 0;
        border-left: 4px solid var(--accent-blue);
    }
    
    .stack-layer.external { border-left-color: var(--accent-purple); }
    .stack-layer.processing { border-left-color: var(--accent-orange); }
    .stack-layer.runtime { border-left-color: var(--accent-green); }

    .path-section {
        background: var(--bg-secondary);
        border-radius: 12px;
        margin: 1.5rem 0;
        overflow: hidden;
        border: 1px solid var(--border-color);
    }

    .path-header {
        display: flex;
        align-items: center;
        padding: 1rem 1.5rem;
        background: var(--bg-card);
        gap: 1rem;
    }

    .path-number {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: var(--accent-orange); /* Default Admin guide color */
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 1rem;
        color: white;
    }
    
    .path-title { font-size: 1.25rem; font-weight: 600; }
    .path-subtitle { color: var(--text-secondary); font-size: 0.9rem; }
    .path-content { padding: 1.5rem; }

    /* Tutorial Components */
    .concept-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 1.5rem;
        margin: 1.5rem 0;
    }

    .concept-card {
        background: var(--bg-secondary);
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid var(--border-color);
    }
    .concept-card.database { border-left: 4px solid var(--accent-green); }
    .concept-card.ai { border-left: 4px solid var(--accent-purple); }

    .stat-row {
        display: flex;
        justify-content: space-between;
        padding: 0.5rem 0;
        border-bottom: 1px solid var(--border-color);
    }
    
    .tab-section {
        background: var(--bg-secondary);
        border-radius: 12px;
        margin: 1.5rem 0;
        overflow: hidden;
        border: 1px solid var(--border-color);
    }
    
    .tab-header {
        display: flex;
        align-items: center;
        padding: 1rem 1.5rem;
        background: var(--bg-card);
        gap: 1rem;
    }
    
    .tab-number {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: var(--accent-blue);
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 0.9rem;
        color: white;
    }

    .flow-diagram {
        background: var(--bg-primary);
        border-radius: 8px;
        padding: 1rem;
        font-family: 'Courier New', monospace;
        font-size: 0.9rem;
        margin: 1rem 0;
        overflow-x: auto;
    }
    .flow-arrow { color: var(--accent-blue); }

    /* Setup Guide Components */
    .req-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 1rem;
        margin: 1rem 0;
    }

    .req-card {
        background: var(--bg-card);
        border-radius: 8px;
        padding: 1rem;
        border-left: 4px solid var(--accent-green);
    }
    
    .checklist {
        background: var(--bg-secondary);
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1.5rem 0;
        border: 2px solid var(--accent-green);
    }
    
    .check-item {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.5rem 0;
    }
    .check-icon {
        color: var(--accent-green);
        font-size: 1.25rem;
    }
    
    /* Navigation Footer Links */
    .link-row {
        display: flex;
        gap: 1rem;
        margin-top: 2rem;
        flex-wrap: wrap;
    }

    .back-link {
        display: inline-block;
        padding: 0.75rem 1.5rem;
        background: var(--accent-blue);
        color: white;
        text-decoration: none;
        border-radius: 8px;
        font-weight: 600;
        transition: background 0.2s;
    }
    .page-admin .back-link { background: var(--accent-orange); }
    .page-setup .back-link { background: var(--accent-green); }

    .back-link:hover { opacity: 0.9; }

    .link-secondary {
        display: inline-block;
        padding: 0.75rem 1.5rem;
        background: var(--bg-secondary);
        color: var(--text-primary);
        text-decoration: none;
        border-radius: 8px;
        font-weight: 600;
        border: 1px solid var(--border-color);
        transition: border-color 0.2s;
    }

    .link-secondary:hover {
        border-color: var(--accent-blue);
    }
"""

def get_nav_bar(active_page: str = "") -> str:
    """Generate navigation bar HTML with active page highlighted."""
    
    # Define active states
    states = {
        'hub': '', 
        'tutorial': '', 
        'admin': '', 
        'setup': '', 
        'api': '', 
        'redoc': ''
    }
    if active_page in states:
        states[active_page] = 'active'
        
    return f"""
    <nav class="top-nav">
        <a href="/api/v1/docs-hub" class="nav-brand">
            <span>📚</span> PSIRT Docs
        </a>
        <div class="nav-links">
            <a href="/api/v1/docs-hub" class="nav-link hub {states['hub']}">Hub</a>
            <a href="/api/v1/tutorial" class="nav-link tutorial {states['tutorial']}">Tutorial</a>
            <a href="/api/v1/admin-guide" class="nav-link admin {states['admin']}">Admin Guide</a>
            <a href="/api/v1/setup-guide" class="nav-link setup {states['setup']}">Setup Guide</a>
            <a href="/api/v1/api-reference" class="nav-link api {states['api']}">API Reference</a>
            <a href="/api/v1/redoc" class="nav-link api {states['redoc']}">ReDoc</a>
        </div>
    </nav>
    """

def get_page_template(title: str, active_page: str, content: str, page_class: str = "") -> str:
    """
    Wraps content in the standard HTML boilerplate.
    
    Args:
        title: Page title for <title> tag
        active_page: Key for get_nav_bar to highlight current page
        content: HTML content for the body main-content
        page_class: Optional class for body/content styling (e.g., 'page-admin')
    """
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PSIRT Analyzer - {title}</title>
    <style>
        {SHARED_STYLES}
    </style>
</head>
<body>
    <div class="{page_class}"> <!-- Wrapper for page-specific styling scope -->
        {get_nav_bar(active_page)}

        <div class="main-content">
            {content}
        </div>
    </div>
</body>
</html>
"""
