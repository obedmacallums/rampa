# Potree 1.8.2 (vendored)

Static build of [Potree](https://github.com/potree/potree) 1.8.2 (BSD
2-clause, see LICENSE) serving the 3D COPC viewer. Layout mirrors the
upstream release (`build/potree` + `libs`) so Potree's internal relative
paths (workers, lazylibs, resources) resolve from `/potree/`.

Local patch: the decoder workers hardcode absolute `importScripts('/libs/…')`
paths that assume deployment at the site root; they are rewritten to
`/potree/libs/…` (EptLaszipDecoderWorker.js, EptBinaryDecoderWorker.js,
EptZstandardDecoderWorker.js). Re-apply when upgrading:

    sed -i '' "s|importScripts('/libs/|importScripts('/potree/libs/|g" build/potree/workers/Ept*Worker.js

`build/potree/potree.js.map` is dropped (24 MB). Unused upstream extras
(examples, docs, sample pointclouds, Cesium, three.js lib copy) are not
vendored.
