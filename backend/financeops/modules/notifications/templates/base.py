BASE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI',
            sans-serif; background: #0f172a; color: #e2e8f0;
            margin: 0; padding: 0; }}
    .container {{ max-width: 600px; margin: 40px auto; padding: 0 20px; }}
    .card {{ background: #1e293b; border: 1px solid #334155;
             border-radius: 12px; padding: 32px; }}
    .logo {{ font-size: 20px; font-weight: 700; color: #fff;
             margin-bottom: 24px; }}
    h1 {{ font-size: 22px; color: #fff; margin: 0 0 12px; }}
    p {{ color: #94a3b8; line-height: 1.6; margin: 0 0 16px; }}
    .btn {{ display: inline-block; background: #2563eb; color: #fff;
            text-decoration: none; padding: 12px 24px;
            border-radius: 8px; font-weight: 600; margin: 8px 0; }}
    .code {{ font-family: monospace; font-size: 28px; font-weight: 700;
             color: #fff; background: #0f172a; border: 1px solid #334155;
             border-radius: 8px; padding: 12px 24px;
             letter-spacing: 6px; text-align: center;
             display: block; margin: 16px 0; }}
    .footer {{ margin-top: 32px; font-size: 12px; color: #64748b;
               text-align: center; }}
    .warning {{ background: #451a03; border: 1px solid #92400e;
                border-radius: 8px; padding: 12px 16px;
                color: #fbbf24; font-size: 14px; margin: 16px 0; }}
    .success {{ background: #052e16; border: 1px solid #166534;
                border-radius: 8px; padding: 12px 16px;
                color: #4ade80; font-size: 14px; margin: 16px 0; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="card">
      <div class="logo">FinanceOps</div>
      {content}
    </div>
    <div class="footer">
      FinanceOps - Enterprise Finance Platform<br>
      <a href="{unsubscribe_url}" style="color: #64748b;">
        Manage notifications
      </a>
    </div>
  </div>
</body>
</html>
"""


def render_template(content: str, **kwargs: str) -> str:
    payload = {"unsubscribe_url": "#", **kwargs}
    return BASE_TEMPLATE.format(content=content, **payload)
