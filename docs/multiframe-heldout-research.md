# Stage 063 — independent withheld landmarks across multiple frames

A good training fit across several frames can still conceal incorrect
measurements at different points in the level. Stage 063 combines two
already tested local-only checks:

1. Each frame independently fits four or more **training landmarks** and
   verifies 2–32 **held-out landmarks that never participate in fitting**.
2. Across 2–32 captures, every training and held-out landmark must preserve
   the exact same ID and source-level coordinates. The camera offset may
   change, but scale must remain consistent under the existing axis-aligned
   mathematical hypothesis.

Mismatched or relabeled landmarks, duplicate source coordinates, invalid
frame IDs, large held-out errors, axis flips, excessive zoom or drift and
corrupt private inputs all fail closed. This tool does not discover objects,
decode game art, establish collision masks or reproduce actual iOS camera
behavior.

## Private-only use

A JSON file under `local_reports/` supplies an array of frames. Each
frame has the same schema accepted by `heldout_alignment`:

```json
{
  "frames": [
    {
      "frame_id": "fictional-01",
      "anchors": [
        {"id":"training-a","level_xy":[0,0],"screen_xy":[20,100]},
        {"id":"training-b","level_xy":[10,5],"screen_xy":[40,85]},
        {"id":"training-c","level_xy":[40,25],"screen_xy":[100,25]},
        {"id":"training-d","level_xy":[90,55],"screen_xy":[200,-65]}
      ],
      "holdout_anchors": [
        {"id":"reserved-a","level_xy":[30,70],"screen_xy":[80,-110]},
        {"id":"reserved-b","level_xy":[75,15],"screen_xy":[170,55]}
      ]
    },
    {
      "frame_id": "fictional-02",
      "anchors": [
        {"id":"training-a","level_xy":[0,0],"screen_xy":[50,-15]},
        {"id":"training-b","level_xy":[10,5],"screen_xy":[70,-30]},
        {"id":"training-c","level_xy":[40,25],"screen_xy":[130,-90]},
        {"id":"training-d","level_xy":[90,55],"screen_xy":[230,-180]}
      ],
      "holdout_anchors": [
        {"id":"reserved-a","level_xy":[30,70],"screen_xy":[110,-225]},
        {"id":"reserved-b","level_xy":[75,15],"screen_xy":[200,-60]}
      ]
    }
  ]
}
```

```sh
PYTHONPATH=src python -m heman_tools.multiframe_heldout \
  --frames local_reports/fictional-multiframe-holdout.json \
  --out local_reports/fictional-multiframe-summary.json \
  --max-fit-residual-px 2 \
  --max-holdout-residual-px 2 \
  --max-relative-scale-drift 0.02

PYTHONPATH=src python -m unittest discover -s tests -v
```

The example is completely synthetic. The program reads only private numerical
JSON, never the IPA, image frames, assets or extracted level resources.
Results contain scale, camera offsets and aggregated errors, but not source
landmark coordinates or their measured pixel positions.

## Evidence boundary

A successful check establishes **only numerical consistency of a deliberately
restricted axis-aligned fit**, based on user-provided point identities. It
does not verify the chosen identities, the original iOS camera model,
pixel-to-world scale, physical collision geometry or gameplay. Source
resources and real measurements must stay outside public GitHub and Actions.

20 synthetic regressions test correct/incorrect held-out points, zoom,
reflections, changed names/source positions, duplicate frames, private paths
and noise. Gate merging on all current-head Python GCC/Clang CI jobs.
