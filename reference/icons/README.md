**Generated file — do not edit. Run `python scripts/portfolio.py icons generate`.**


# Icon reference

Browsable slug catalogue for Mermaid `architecture-beta` diagrams. This directory is repository-only documentation (outside `docs/`) and is **not** part of the MkDocs site.

Regenerate with `python scripts/portfolio.py icons generate`.

## Why these packs are vendored

The Iconify JSON files under `docs/assets/mermaid-icons/` are committed snapshots so site builds stay deterministic and offline for icon assets: no CDN or API fetch at build or browse time for the packs themselves, usable on restricted networks, and immune to upstream removal of a key. Refreshing a pack is an explicit maintainer action, not an automatic sync.

## Why contact sheets (not one file per icon)

Showing every icon without rasterising still needs the SVG bodies once. Per-icon previews meant ~2965 committed files; contact sheets keep the same visual coverage in **51** SVG files (80 icons per full sheet). Byte volume is essentially unchanged — that is inherent to shipping all bodies. History still holds deleted preview blobs.

## Collections

- [AWS Icons](aws.md) (`aws`) — 867 icons; upstream version `23.0`; snapshot `2026-01-30T00:00:00+00:00`; license [CC-BY-ND-2.0](https://github.com/awslabs/aws-icons-for-plantuml/blob/main/LICENSE)
- [SVG Logos](logos.md) (`logos`) — 2098 icons; upstream version not recorded; snapshot `2026-03-28T07:03:20+00:00`; license [CC0-1.0](https://raw.githubusercontent.com/gilbarbara/logos/master/LICENSE.txt)

## How sheets are grouped and chunked

- **`aws`:** all keys sorted, chunked into 80s → `sheets/aws-001.svg`, `aws-002.svg`, …
- **`logos`:** group by initial (`a`–`z`, else `0`), then chunk → `sheets/logos-<group>-<NNN>.svg`; letter indexes live under `logos/<group>.md`.

## How to read a cell coordinate

Each index bullet ends with a sheet link and a cell like `r5c1`: **0-based** `row` and `column` inside that sheet (`r0c0` is top-left). The full slug, display name, and Mermaid usage example are on the same line for `Ctrl+F` / GitHub code search.

## Sheet gallery

### AWS Icons (`aws`)

- [![aws-001](sheets/aws-001.svg)](sheets/aws-001.svg) — 80 icons (`activate` … `backup-recovery-point-objective`)
- [![aws-002](sheets/aws-002.svg)](sheets/aws-002.svg) — 80 icons (`backup-recovery-time-objective` … `cloudwatch-rule`)
- [![aws-003](sheets/aws-003.svg)](sheets/aws-003.svg) — 80 icons (`cloudwatch-rum` … `dynamodb-attributes`)
- [![aws-004](sheets/aws-004.svg)](sheets/aws-004.svg) — 80 icons (`dynamodb-global-secondary-index` … `elemental-mediastore`)
- [![aws-005](sheets/aws-005.svg)](sheets/aws-005.svg) — 80 icons (`elemental-mediatailor` … `healthomics`)
- [![aws-006](sheets/aws-006.svg)](sheets/aws-006.svg) — 80 icons (`healthscribe` … `iot-sitewise-asset-model`)
- [![aws-007](sheets/aws-007.svg)](sheets/aws-007.svg) — 80 icons (`iot-sitewise-asset-properties` … `managed-streaming-for-apache-kafka`)
- [![aws-008](sheets/aws-008.svg)](sheets/aws-008.svg) — 80 icons (`managed-workflows-for-apache-airflow` … `rds-optimized-writes`)
- [![aws-009](sheets/aws-009.svg)](sheets/aws-009.svg) — 80 icons (`rds-proxy-instance` … `simple-storage-service`)
- [![aws-010](sheets/aws-010.svg)](sheets/aws-010.svg) — 80 icons (`simple-storage-service-bucket` … `thinkbox-stoke`)
- [![aws-011](sheets/aws-011.svg)](sheets/aws-011.svg) — 67 icons (`thinkbox-xmesh` … `x-ray`)

### SVG Logos (`logos`)

- [![logos-0-001](sheets/logos-0-001.svg)](sheets/logos-0-001.svg) — 3 icons (`100tb` … `6px`)
- [![logos-a-001](sheets/logos-a-001.svg)](sheets/logos-a-001.svg) — 80 icons (`active-campaign` … `appbaseio-icon`)
- [![logos-a-002](sheets/logos-a-002.svg)](sheets/logos-a-002.svg) — 80 icons (`appcelerator` … `aws-cloudwatch`)
- [![logos-a-003](sheets/logos-a-003.svg)](sheets/logos-a-003.svg) — 52 icons (`aws-codebuild` … `azure-icon`)
- [![logos-b-001](sheets/logos-b-001.svg)](sheets/logos-b-001.svg) — 80 icons (`babel` … `builder-io`)
- [![logos-b-002](sheets/logos-b-002.svg)](sheets/logos-b-002.svg) — 7 icons (`builder-io-icon` … `bunny-net-icon`)
- [![logos-c-001](sheets/logos-c-001.svg)](sheets/logos-c-001.svg) — 80 icons (`c` … `codefactor`)
- [![logos-c-002](sheets/logos-c-002.svg)](sheets/logos-c-002.svg) — 80 icons (`codefactor-icon` … `cyclejs`)
- [![logos-c-003](sheets/logos-c-003.svg)](sheets/logos-c-003.svg) — 2 icons (`cypress` … `cypress-icon`)
- [![logos-d-001](sheets/logos-d-001.svg)](sheets/logos-d-001.svg) — 80 icons (`d3` … `dreamfactory`)
- [![logos-d-002](sheets/logos-d-002.svg)](sheets/logos-d-002.svg) — 20 icons (`dreamhost` … `dyndns`)
- [![logos-e-001](sheets/logos-e-001.svg)](sheets/logos-e-001.svg) — 68 icons (`eager` … `express`)
- [![logos-f-001](sheets/logos-f-001.svg)](sheets/logos-f-001.svg) — 71 icons (`fabric` … `fuchsia`)
- [![logos-g-001](sheets/logos-g-001.svg)](sheets/logos-g-001.svg) — 80 icons (`galliumos` … `google-marketing-platform`)
- [![logos-g-002](sheets/logos-g-002.svg)](sheets/logos-g-002.svg) — 53 icons (`google-meet` … `gwt`)
- [![logos-h-001](sheets/logos-h-001.svg)](sheets/logos-h-001.svg) — 73 icons (`hack` … `hyperapp`)
- [![logos-i-001](sheets/logos-i-001.svg)](sheets/logos-i-001.svg) — 40 icons (`ibm` … `itsalive-icon`)
- [![logos-j-001](sheets/logos-j-001.svg)](sheets/logos-j-001.svg) — 41 icons (`jade` … `jwt-icon`)
- [![logos-k-001](sheets/logos-k-001.svg)](sheets/logos-k-001.svg) — 47 icons (`kafka` … `kustomer`)
- [![logos-l-001](sheets/logos-l-001.svg)](sheets/logos-l-001.svg) — 58 icons (`languagetool` … `lynda`)
- [![logos-m-001](sheets/logos-m-001.svg)](sheets/logos-m-001.svg) — 80 icons (`macos` … `micro-python`)
- [![logos-m-002](sheets/logos-m-002.svg)](sheets/logos-m-002.svg) — 71 icons (`microcosm` … `myth`)
- [![logos-n-001](sheets/logos-n-001.svg)](sheets/logos-n-001.svg) — 61 icons (`naiveui` … `nx`)
- [![logos-o-001](sheets/logos-o-001.svg)](sheets/logos-o-001.svg) — 55 icons (`oauth` … `oxc-icon-dark`)
- [![logos-p-001](sheets/logos-p-001.svg)](sheets/logos-p-001.svg) — 80 icons (`p5js` … `postman-icon`)
- [![logos-p-002](sheets/logos-p-002.svg)](sheets/logos-p-002.svg) — 51 icons (`pouchdb` … `pyup`)
- [![logos-q-001](sheets/logos-q-001.svg)](sheets/logos-q-001.svg) — 16 icons (`q` … `qwik-icon`)
- [![logos-r-001](sheets/logos-r-001.svg)](sheets/logos-r-001.svg) — 80 icons (`r-lang` … `rome-icon`)
- [![logos-r-002](sheets/logos-r-002.svg)](sheets/logos-r-002.svg) — 15 icons (`ros` … `rxdb`)
- [![logos-s-001](sheets/logos-s-001.svg)](sheets/logos-s-001.svg) — 80 icons (`safari` … `snowflake-icon`)
- [![logos-s-002](sheets/logos-s-002.svg)](sheets/logos-s-002.svg) — 80 icons (`snowpack` … `streamlit`)
- [![logos-s-003](sheets/logos-s-003.svg)](sheets/logos-s-003.svg) — 43 icons (`strider` … `sysdig-icon`)
- [![logos-t-001](sheets/logos-t-001.svg)](sheets/logos-t-001.svg) — 80 icons (`t3` … `twilio`)
- [![logos-t-002](sheets/logos-t-002.svg)](sheets/logos-t-002.svg) — 13 icons (`twilio-icon` … `typo3-icon`)
- [![logos-u-001](sheets/logos-u-001.svg)](sheets/logos-u-001.svg) — 28 icons (`ubuntu` … `uwsgi`)
- [![logos-v-001](sheets/logos-v-001.svg)](sheets/logos-v-001.svg) — 46 icons (`v8` … `vwo`)
- [![logos-w-001](sheets/logos-w-001.svg)](sheets/logos-w-001.svg) — 69 icons (`w3c` … `wufoo`)
- [![logos-x-001](sheets/logos-x-001.svg)](sheets/logos-x-001.svg) — 16 icons (`x` … `xwiki-icon`)
- [![logos-y-001](sheets/logos-y-001.svg)](sheets/logos-y-001.svg) — 13 icons (`yahoo` … `yugabyte-icon`)
- [![logos-z-001](sheets/logos-z-001.svg)](sheets/logos-z-001.svg) — 26 icons (`zabbix` … `zwave`)

## Display names

Display names are a mechanical humanisation of the upstream key (split on `-`, capitalise tokens). They are approximate — acronyms and official product casing are often wrong (`Ec2`, `Cloudfront`). The slug and Mermaid usage example are authoritative.

## How to use a slug

Slug format is `<pack>:<icon-key>` (upstream key verbatim). Example:

````markdown
```mermaid
architecture-beta
    service api(aws:api-gateway)[API Gateway]
    service fn(aws:lambda)[Lambda]
    api:R --> L:fn
```
````

Find slugs in the per-collection / per-letter pages linked above, or search this folder for `aws:` / `logos:` plus a keyword.

## Licensing

Repository source is MIT; vendored icon collections and generated contact sheets are third-party works under their own terms. See [`THIRD_PARTY_NOTICES.md`](../../THIRD_PARTY_NOTICES.md).

## Deferred

Upstream sync automation, curated official display names, alias/deprecated-slug registry, fuzzy suggestions, interactive search UI, MkDocs nav integration, per-icon luminance backgrounds, and trimming packs to only referenced icons are out of scope for this iteration.
