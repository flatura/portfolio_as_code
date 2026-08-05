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

    // Material exposes the relative path to the site root for this page.
    // Do not use document.baseURI alone — it is the page URL and nests
    // assets under /projects/... on nested pages.
    const siteBase =
      JSON.parse(document.getElementById("__config").textContent).base || "."
    const base = new URL(
      siteBase.endsWith("/") ? siteBase : `${siteBase}/`,
      document.location.href
    ).href
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