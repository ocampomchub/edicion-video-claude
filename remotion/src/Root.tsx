import React from "react";
import { Composition } from "remotion";
import { Subtitles } from "./Subtitles";
import { Graphics } from "./Graphics";
import { SubtitlesSchema, GraphicsSchema } from "./types";

const FPS = 30;
const WIDTH = 1080;
const HEIGHT = 1920;

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="Subtitles"
        component={Subtitles}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
        durationInFrames={FPS * 10}
        schema={SubtitlesSchema}
        defaultProps={{
          duration: 10,
          style: {
            font: "Playfair Display",
            weight: 600,
            color: "#F2B01E",
            emphasisColor: "#F4EDE2",
            shadowOpacity: 0.4,
            bottomSafePct: 0.22,
            entryRisePx: 12,
            entryFrames: 6,
            emphasisScale: 1.15,
          },
          cards: [],
        }}
        calculateMetadata={async ({ props }) => ({
          durationInFrames: Math.max(1, Math.round(props.duration * FPS)),
        })}
      />
      <Composition
        id="Graphics"
        component={Graphics}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
        durationInFrames={FPS * 10}
        schema={GraphicsSchema}
        defaultProps={{
          duration: 10,
          palette: { amber: "#F2B01E", malva: "#9B7EC8", magenta: "#C4384F", crema: "#F4EDE2" },
          graphics: [],
        }}
        calculateMetadata={async ({ props }) => ({
          durationInFrames: Math.max(1, Math.round(props.duration * FPS)),
        })}
      />
    </>
  );
};
