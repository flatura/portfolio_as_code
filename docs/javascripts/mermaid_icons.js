;(async () => {
  const sources = new WeakMap()
  let mermaidApi

  const theme = () =>
    document.body.getAttribute("data-md-color-scheme") === "slate"
      ? "dark"
      : "default"

  async function ensureMermaid() {
    if (mermaidApi) return mermaidApi

    const mod = await import(
      "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs"
    )
    mermaidApi = mod.default ?? mod

    // Resolve against the site root (script lives in javascripts/), not the
    // current page URL — document.baseURI nests assets under /projects/...
    const scriptSrc = [...document.getElementsByTagName("script")]
      .map((s) => s.src)
      .find((src) => src.includes("mermaid_icons.js"))
    const base = scriptSrc
      ? new URL("../", scriptSrc).href
      : document.baseURI
    // #region agent log
    fetch("http://127.0.0.1:7255/ingest/a3feb566-e5c4-48e2-9e6a-623c00f794d0", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Debug-Session-Id": "ae0d78",
      },
      body: JSON.stringify({
        sessionId: "ae0d78",
        runId: "post-fix",
        hypothesisId: "A",
        location: "mermaid_icons.js:base",
        message: "icon pack base resolution",
        data: {
          page: location.href,
          baseURI: document.baseURI,
          scriptSrc: scriptSrc || null,
          base,
          aws: new URL("assets/mermaid-icons/aws-icons.json", base).href,
        },
        timestamp: Date.now(),
      }),
    }).catch(() => {})
    // #endregion
    const load = async (path, label) => {
      const res = await fetch(new URL(path, base))
      if (!res.ok) throw new Error(`${label} failed: ${res.status} ${res.url}`)
      return res.json()
    }

    const [awsIcons, logosIcons] = await Promise.all([
      load("assets/mermaid-icons/aws-icons.json", "AWS icon pack"),
      load("assets/mermaid-icons/logos.json", "Logos icon pack"),
    ])

    mermaidApi.registerIconPacks([
      { name: "aws", icons: awsIcons },
      { name: "logos", icons: logosIcons },
    ])

    return mermaidApi
  }

  async function renderMermaidBlocks() {
    try {
      const api = await ensureMermaid()
      api.initialize({
        startOnLoad: false,
        securityLevel: "loose",
        theme: theme(),
      })

      for (const block of document.querySelectorAll(".mermaid-custom")) {
        const source = block.textContent.trim()
        if (!source) continue

        const wrapper = document.createElement("div")
        wrapper.className = "mermaid"
        sources.set(wrapper, source)

        const target =
          block.tagName === "CODE" && block.parentElement?.tagName === "PRE"
            ? block.parentElement
            : block
        target.replaceWith(wrapper)
      }

      const blocks = [...document.querySelectorAll(".mermaid")].filter((el) =>
        sources.has(el)
      )

      for (const [index, wrapper] of blocks.entries()) {
        const source = sources.get(wrapper)
        wrapper.innerHTML = ""
        try {
          const { svg } = await api.render(
            `mermaid-custom-${Date.now()}-${index}`,
            source
          )
          wrapper.innerHTML = svg
        } catch (e) {
          console.error("[mermaid-icons] render failed", e)
          wrapper.innerHTML = `<pre class="mermaid-error">${String(e)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")}</pre>`
        }
      }
    } catch (e) {
      console.error("[mermaid-icons]", e)
    }
  }

  const run = () => {
    renderMermaidBlocks().catch((e) =>
      console.error("[mermaid-icons] unhandled error", e)
    )
  }

  if (typeof document$ !== "undefined") {
    document$.subscribe(run)
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run)
  } else {
    run()
  }

  new MutationObserver((mutations) => {
    if (
      mutations.some(
        (m) =>
          m.type === "attributes" && m.attributeName === "data-md-color-scheme"
      )
    ) {
      run()
    }
  }).observe(document.body, {
    attributes: true,
    attributeFilter: ["data-md-color-scheme"],
  })
})()