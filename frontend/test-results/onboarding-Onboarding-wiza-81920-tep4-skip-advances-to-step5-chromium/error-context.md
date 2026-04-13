# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - link "Skip to main content" [ref=e2] [cursor=pointer]:
    - /url: "#main-content"
  - main [ref=e3]:
    - generic [ref=e4]:
      - heading "Page Not Found" [level=1] [ref=e5]
      - paragraph [ref=e6]: The page you requested does not exist.
      - link "Go To Dashboard" [ref=e7] [cursor=pointer]:
        - /url: /mis
  - generic [ref=e9]:
    - paragraph [ref=e10]:
      - text: We use essential cookies only for authentication and security. No tracking or advertising cookies.
      - link "Learn more" [ref=e11] [cursor=pointer]:
        - /url: /legal/cookies
    - button "Accept Cookies" [ref=e12] [cursor=pointer]
  - region "Notifications alt+T"
  - alert [ref=e13]
```