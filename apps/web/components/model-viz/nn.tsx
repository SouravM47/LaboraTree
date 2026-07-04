"use client";

import type { ModelTrace, TestRow } from "@/lib/api";
import type { TestProps, TrainProps } from "./shared";

/** Neural-network family — a LITERAL network: neuron circles joined by the REAL learned weights
 *  (thicker = stronger, green = positive, red = negative). Training loops a forward pulse
 *  (signals flow left→right) then a backprop sweep (error flows right→left, adjusting weights). */

type Fwd = {
  input: number[];
  input_names: string[];
  hidden: number[];
  output: number;
  w1?: number[][];
  w2?: number[];
};

const X_IN = 70;
const X_HID = 250;
const X_OUT = 400;
const R_IN = 11;
const R_HID = 14;
const R_OUT = 18;

function edgeColor(w: number) {
  return w >= 0 ? "#6DB33F" : "#C0392B";
}
function edgeWidth(w: number, max: number) {
  return 0.6 + (Math.abs(w) / (max || 1)) * 3.2;
}

function NetworkDiagram({
  fwd,
  animate,
  caption,
}: {
  fwd: Fwd;
  animate: boolean;
  caption: string;
}) {
  const nIn = fwd.input_names.length;
  const nHid = fwd.hidden.length;
  const H = Math.max(nIn, nHid) * 34 + 40;
  const yIn = (i: number) => 26 + ((H - 52) / Math.max(1, nIn - 1)) * i;
  const yHid = (j: number) => 26 + ((H - 52) / Math.max(1, nHid - 1)) * j;
  const yOut = H / 2;
  const w1 = fwd.w1 ?? [];
  const w2 = fwd.w2 ?? [];
  const maxW = Math.max(
    0.001,
    ...w1.flat().map((v) => Math.abs(v)),
    ...w2.map((v) => Math.abs(v)),
  );

  return (
    <div className="overflow-x-auto rounded-lg border border-line bg-white p-2">
      <style>{`
        @keyframes nnFwd { 0% { stroke-dashoffset: 24; opacity:.35 } 45% { stroke-dashoffset: 0; opacity:1 } 55% { opacity:1 } 100% { stroke-dashoffset: 0; opacity:.35 } }
        @keyframes nnBack { 0%,55% { opacity: 0 } 65% { opacity: .9 } 95% { opacity: 0 } 100% { opacity: 0 } }
      `}</style>
      <svg viewBox={`0 0 470 ${H}`} width="100%" style={{ minWidth: 430 }} role="img" aria-label="neural network">
        {/* input → hidden edges (real weights) */}
        {fwd.input_names.map((_, i) =>
          Array.from({ length: nHid }, (_, j) => {
            const w = w1[i]?.[j] ?? 0.2;
            return (
              <line
                key={`e${i}-${j}`}
                x1={X_IN + R_IN}
                y1={yIn(i)}
                x2={X_HID - R_HID}
                y2={yHid(j)}
                stroke={edgeColor(w)}
                strokeWidth={edgeWidth(w, maxW)}
                strokeDasharray={animate ? "6 3" : undefined}
                style={animate ? { animation: `nnFwd 3.2s ease-in-out infinite` } : { opacity: 0.8 }}
              />
            );
          }),
        )}
        {/* hidden → output edges */}
        {fwd.hidden.map((_, j) => {
          const w = w2[j] ?? 0.2;
          return (
            <line
              key={`o${j}`}
              x1={X_HID + R_HID}
              y1={yHid(j)}
              x2={X_OUT - R_OUT}
              y2={yOut}
              stroke={edgeColor(w)}
              strokeWidth={edgeWidth(w, maxW)}
              strokeDasharray={animate ? "6 3" : undefined}
              style={
                animate
                  ? { animation: `nnFwd 3.2s ease-in-out infinite`, animationDelay: "0.5s" }
                  : { opacity: 0.8 }
              }
            />
          );
        })}
        {/* backprop sweep (training only): error flows backwards in gold */}
        {animate && (
          <>
            {fwd.hidden.map((_, j) => (
              <line
                key={`b${j}`}
                x1={X_OUT - R_OUT}
                y1={yOut}
                x2={X_HID + R_HID}
                y2={yHid(j)}
                stroke="#C9A227"
                strokeWidth={2}
                strokeDasharray="3 4"
                style={{ animation: "nnBack 3.2s ease-in-out infinite" }}
              />
            ))}
            {fwd.input_names.map((_, i) =>
              Array.from({ length: nHid }, (_, j) => (
                <line
                  key={`bb${i}-${j}`}
                  x1={X_HID - R_HID}
                  y1={yHid(j)}
                  x2={X_IN + R_IN}
                  y2={yIn(i)}
                  stroke="#C9A227"
                  strokeWidth={1.4}
                  strokeDasharray="3 4"
                  style={{ animation: "nnBack 3.2s ease-in-out infinite", animationDelay: "0.35s" }}
                />
              )),
            )}
          </>
        )}
        {/* input neurons + values + names */}
        {fwd.input_names.map((name, i) => (
          <g key={`in${i}`}>
            <circle cx={X_IN} cy={yIn(i)} r={R_IN} fill="#EAF2F8" stroke="#2E6C8E" strokeWidth={1.5} />
            <text x={X_IN} y={yIn(i) + 3} fontSize={8} textAnchor="middle" fill="#14342A" fontWeight={600}>
              {fwd.input[i]}
            </text>
            <text x={X_IN - R_IN - 4} y={yIn(i) + 3} fontSize={8.5} textAnchor="end" fill="#7C8A80">
              {name}
            </text>
          </g>
        ))}
        {/* hidden neurons with activation bars */}
        {fwd.hidden.map((h, j) => (
          <g key={`h${j}`}>
            <circle cx={X_HID} cy={yHid(j)} r={R_HID} fill="#E4F3DA" stroke="#3F8F5B" strokeWidth={1.5} />
            <text x={X_HID} y={yHid(j) + 3} fontSize={8} textAnchor="middle" fill="#14342A" fontWeight={600}>
              {h}
            </text>
          </g>
        ))}
        {/* output neuron */}
        <circle cx={X_OUT} cy={yOut} r={R_OUT} fill="#14342A" />
        <text x={X_OUT} y={yOut + 3.5} fontSize={9} textAnchor="middle" fill="#fff" fontWeight={700}>
          {fwd.output}
        </text>
        <text x={X_OUT} y={yOut + R_OUT + 12} fontSize={8.5} textAnchor="middle" fill="#7C8A80">
          output
        </text>
        {/* layer captions */}
        <text x={X_IN} y={12} fontSize={9} textAnchor="middle" fill="#2E6C8E" fontWeight={600}>
          inputs
        </text>
        <text x={X_HID} y={12} fontSize={9} textAnchor="middle" fill="#3F8F5B" fontWeight={600}>
          hidden layer
        </text>
      </svg>
      <p className="px-1 pt-1 text-[10px] text-muted">{caption}</p>
    </div>
  );
}

export function Train({ trace }: TrainProps) {
  if (!trace.forward) return null;
  return (
    <div>
      <p className="mb-1 text-[11px] text-muted">
        The literal network, drawn with its <b>real learned weights</b>: line thickness = how strong
        the connection is, <span className="text-green-700">green pushes up</span>,{" "}
        <span className="text-red-600">red pushes down</span>. Watch the loop: signals flow{" "}
        <b>forward</b> (dashed green/red), the output is compared to the truth, and the error sweeps{" "}
        <b>backwards in gold (backpropagation)</b>, nudging every weight to do better next time.
        Thousands of these loops = training. CNN/LSTM/GRU stack more layers, same loop.
      </p>
      <NetworkDiagram
        fwd={trace.forward}
        animate
        caption="forward pass (green/red dashes) → error → backprop sweep (gold, right-to-left) → weights adjust — repeating"
      />
    </div>
  );
}

export function Test({ trace, row }: TestProps) {
  if (!row.hidden) return null;
  const fwd = {
    input: row.input ?? [],
    input_names: trace.features,
    hidden: row.hidden,
    output: row.output ?? 0,
    w1: trace.forward?.w1,
    w2: trace.forward?.w2,
  };
  return (
    <div>
      <p className="mb-1 text-[11px] text-muted">
        This row&apos;s values flow through the trained network — each hidden neuron computes a
        weighted mix of the inputs (then squashes it), and the output combines the hidden neurons:
      </p>
      <NetworkDiagram
        fwd={fwd}
        animate={false}
        caption="numbers in the circles are THIS row's actual activations at each neuron"
      />
    </div>
  );
}
