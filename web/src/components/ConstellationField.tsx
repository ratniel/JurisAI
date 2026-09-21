import { useRef } from "react";
import { motion, useMotionValue, useSpring, useTransform } from "motion/react";
import "../styles/constellation.css";

const nodes = [
  { id: "a", x: 58, y: 80, label: "ELIGIBILITY", side: "left" },
  { id: "b", x: 178, y: 45, label: "STATE", side: "left" },
  { id: "c", x: 248, y: 154, label: "BENEFITS", side: "left" },
  { id: "d", x: 106, y: 246, label: "SCHEMES", side: "left" },
  { id: "e", x: 198, y: 326, label: "SUPPORT", side: "left" },
  { id: "f", x: 116, y: 422, label: "ACCESS", side: "left" },
  { id: "g", x: 1160, y: 72, label: "FARMERS", side: "right" },
  { id: "h", x: 1284, y: 145, label: "HOUSING", side: "right" },
  { id: "i", x: 1176, y: 226, label: "WOMEN", side: "right" },
  { id: "j", x: 1305, y: 310, label: "PENSIONS", side: "right" },
  { id: "k", x: 1184, y: 384, label: "HEALTH", side: "right" },
  { id: "l", x: 1306, y: 454, label: "EDUCATION", side: "right" },
] as const;

const paths = [
  "M58 80 C100 58 130 47 178 45", "M58 80 C96 126 156 155 248 154",
  "M178 45 C210 75 230 111 248 154", "M248 154 C213 202 160 231 106 246",
  "M106 246 C130 281 161 310 198 326", "M198 326 C157 351 127 386 116 422",
  "M1160 72 C1210 68 1247 100 1284 145", "M1160 72 C1162 130 1168 177 1176 226",
  "M1284 145 C1251 180 1216 207 1176 226", "M1176 226 C1224 263 1266 290 1305 310",
  "M1305 310 C1268 347 1227 373 1184 384", "M1184 384 C1225 411 1268 437 1306 454",
] as const;

/** Decorative, cursor-reactive legal-scheme constellation for the home hero. */
export function ConstellationField() {
  const fieldRef = useRef<HTMLDivElement>(null);
  const pointerX = useMotionValue(0);
  const pointerY = useMotionValue(0);
  const smoothX = useSpring(pointerX, { stiffness: 95, damping: 24, mass: 0.7 });
  const smoothY = useSpring(pointerY, { stiffness: 95, damping: 24, mass: 0.7 });
  const parallaxX = useTransform(smoothX, [-1, 1], [5, -5]);
  const parallaxY = useTransform(smoothY, [-1, 1], [4, -4]);

  function trackPointer(event: React.PointerEvent<HTMLDivElement>) {
    if (event.pointerType !== "mouse") return;
    const bounds = event.currentTarget.getBoundingClientRect();
    pointerX.set(((event.clientX - bounds.left) / bounds.width) * 2 - 1);
    pointerY.set(((event.clientY - bounds.top) / bounds.height) * 2 - 1);
    fieldRef.current?.style.setProperty("--pointer-x", `${event.clientX - bounds.left}px`);
    fieldRef.current?.style.setProperty("--pointer-y", `${event.clientY - bounds.top}px`);
    fieldRef.current?.style.setProperty("--pointer-active", "1");
  }

  function clearPointer() {
    pointerX.set(0);
    pointerY.set(0);
    fieldRef.current?.style.setProperty("--pointer-active", "0");
  }

  return (
    <motion.div
      ref={fieldRef}
      className="constellation-field"
      aria-hidden="true"
      onPointerMove={trackPointer}
      onPointerLeave={clearPointer}
      style={{ x: parallaxX, y: parallaxY }}
    >
      <svg className="constellation-svg" viewBox="0 0 1360 500" preserveAspectRatio="none" focusable="false">
        <g className="constellation-curves">
          {paths.map((path, index) => <path key={index} d={path} />)}
        </g>
        <g className="constellation-nodes">
          {nodes.map((node, index) => (
            <g className="constellation-node" key={node.id} style={{ "--node-x": `${node.x / 13.6}%`, "--node-y": `${node.y / 5}%` } as React.CSSProperties}>
              <circle cx={node.x} cy={node.y} r={index % 3 === 0 ? 3.1 : 2.2} />
              <text x={node.x + (node.side === "left" ? 10 : -10)} y={node.y - 9} textAnchor={node.side === "left" ? "start" : "end"}>{node.label}</text>
            </g>
          ))}
        </g>
      </svg>
      <div className="constellation-pointer" />
    </motion.div>
  );
}

export default ConstellationField;
