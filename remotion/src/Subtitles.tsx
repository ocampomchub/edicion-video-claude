import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, Easing } from "remotion";
import { loadFont } from "@remotion/google-fonts/PlayfairDisplay";
import type { SubtitlesProps } from "./types";

const { fontFamily } = loadFont("normal", { weights: ["600"], subsets: ["latin"] });

export const Subtitles: React.FC<SubtitlesProps> = ({ style, cards }) => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();
  const t = frame / fps;

  const activeIndex = cards.findIndex((c) => t >= c.start && t < c.end);
  if (activeIndex === -1) {
    return <AbsoluteFill />;
  }
  const card = cards[activeIndex];
  const cardStartFrame = Math.round(card.start * fps);
  const framesIntoCard = frame - cardStartFrame;

  // Entrada: fade + subida de entryRisePx en entryFrames. Sin karaoke, sin rebotes.
  const entryProgress = interpolate(
    framesIntoCard,
    [0, style.entryFrames],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.quad) }
  );
  const opacity = entryProgress;
  const translateY = (1 - entryProgress) * style.entryRisePx;

  const bottom = height * style.bottomSafePct;

  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center" }}>
      <div
        style={{
          position: "absolute",
          bottom,
          left: 0,
          right: 0,
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          gap: "0.35em",
          opacity,
          transform: `translateY(${translateY}px)`,
          fontFamily,
          fontWeight: style.weight,
          fontSize: 64,
          textShadow: `0 4px 10px rgba(0,0,0,${style.shadowOpacity})`,
          padding: "0 6%",
          textAlign: "center",
        }}
      >
        {card.words.map((w, i) => {
          const isEmphasized = w.emphasize && t >= w.start && t < w.end;
          return (
            <span
              key={i}
              style={{
                color: isEmphasized ? style.emphasisColor : style.color,
                transform: isEmphasized ? `scale(${style.emphasisScale})` : "scale(1)",
                display: "inline-block",
                transition: "transform 0.1s ease-out",
              }}
            >
              {w.text}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
