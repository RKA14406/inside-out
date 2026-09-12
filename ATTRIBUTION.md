# InsideOut asset and model credits

Updated 2026-09-11. Downloaded source files and generated competition copies are retained under `assets/desktop/sources/`; each folder has `metadata.json`. Metadata records source, license, checksum, byte size, and modifications. The manifest carries these credits into the native UI.

## 3D assets

| Local ID | Author / attribution | Publisher source | License |
|---|---|---|---|
| `human_heart` | Kristen Browne; Heidi Schlehlein. 2022. *3D Reference Organ for Heart, Male v1.2.* | [HuBMAP HRA, DOI HBM373.VSTV.568](https://doi.org/10.48539/HBM373.VSTV.568) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| `human_lungs` | Kristen Browne; Heidi Schlehlein. 2022. *3D Reference Organ for Lung, Male v1.2.* | [HuBMAP HRA, DOI HBM787.FWXN.723](https://doi.org/10.48539/HBM787.FWXN.723) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| `antique_camera` | Maximillan Kamps / UX3D, 2018 | [Khronos AntiqueCamera](https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/AntiqueCamera) | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/); separate UX3D mark notice |
| `toy_car` | Eric Chadwick / Darmstadt Graphics Group GmbH; Khronos Group, 2024 | [Khronos CarConcept](https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/CarConcept) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); Khronos trademark/logo terms are separate |
| `lantern` | Microsoft / sbtron: initial version, 2017; source also credits Frank Galligan for Draco compression, 2018 | [Khronos Lantern](https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/Lantern) | CC0 1.0 |
| `water_bottle` | Microsoft, 2017 | [Khronos WaterBottle](https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/WaterBottle) | CC0 1.0 |
| `earth` | InsideOut project | Local four-layer procedural fallback | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) |

The HRA models derive from Visible Human Male data provided by the US National Library of Medicine; HuBMAP is the publisher, and NIH is the funder. The source's complete citation and project credits are preserved locally.

**Modifications:** derived runtime data applies graph transforms, centers/scales geometry, extracts component meshes/textures, and renders retrieval previews. The bottle is split into geometric connected components. Display materials are simplified for VTK; they are not a complete reproduction of GLTF PBR extensions. No original authorship of downloaded models is claimed, and no publisher endorsement is implied.

**CarConcept competition copy.** `CarConcept-original.glb` is retained unchanged. The runtime copy combines 109 imported geometry instances into 11 source-supported assemblies: Body, Hood, Left Door, Right Door, Rear Hatch, Interior, Mechanical, and four wheels. Textures are omitted and the `InteriorSteeringEmblem` node is excluded, neutralizing Khronos/DGG logo presentation while retaining attribution. This also avoids exposing hundreds of tiny material primitives as learning components. The source LICENSE states CC BY 4.0 for model files and separately excludes Khronos trademarks/logos from that license.

**Earth asset decision.** The requested [Earth Core V.1 by Ipay](https://sketchfab.com/3d-models/earth-core-v1-4c3ea4018a7442c4b221d91b8f373a55) was inspected: the publisher page reports 22.6k triangles, 11.5k vertices, and [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Its official download required a logged-in Sketchfab account unavailable on the competition machine. The viewer was not scraped and the Ipay asset is not bundled. Under the requested fallback rule, InsideOut generated a lightweight 7,050-triangle cutaway with four honest runtime parts: Surface / Crust, Mantle, Outer Core, and Inner Core. Layer terminology follows [NASA Earth facts](https://science.nasa.gov/earth/facts/) and [USGS Inside the Earth](https://pubs.usgs.gov/gip/dynamic/inside.html). Surface colours and continent-like patches are stylized, not cartographically accurate.

The antique camera contains an embedded UX3D logo. Its [separate mark notice](assets/desktop/sources/antique_camera/UX3D_MARK_NOTICE.txt) is retained. Do not extract the mark for InsideOut branding or infer permission for use outside the asset. Model copyright terms do not grant independent trademark rights.

Other investigated assets without sufficiently clear model-specific reuse terms were not added to the cache. Availability on GitHub alone is not treated as an asset license.

## Visual encoder

- [OpenCLIP implementation](https://github.com/mlfoundations/open_clip): MIT-licensed open-source code.
- [CLIP ViT-B-32, LAION-2B-s34B-b79K checkpoint](https://huggingface.co/laion/CLIP-ViT-B-32-laion2B-s34B-b79K): source model card declares MIT. The card is retained at `data/weights/OPENCLIP_MODEL_CARD.md`.
- InsideOut uses the image tower only; no text generation or text/filename retrieval is used.

Package distributions retain their upstream licenses and notices. The application uses PySide6/Qt, VTK, OpenCV, MediaPipe, PyTorch, torchvision, trimesh, NumPy, SciPy, Pillow, and OpenCLIP. Review their distribution requirements before making an installer; this build is a local prototype, not a licensing audit for redistribution.

## Optional research, not bundled/runtime dependencies

[NVIDIA PartField](https://github.com/nv-tlabs/PartField) and [DepthART](https://github.com/bulatko/DepthART) were investigated as possible future work. Neither project, its weights, nor an integration adapter is included in the competition repository or runtime. Preserve and review the relevant terms if adding either later.

## Project provenance

The application was implemented with AI assistance. No general open-source license for the project's own code has been selected. External asset attribution and competition originality/disclosure requirements remain applicable; this document does not certify competition eligibility.
