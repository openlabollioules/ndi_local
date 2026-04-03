"use client";

import dynamic from "next/dynamic";
import { useMemo } from "react";

export type ChartType = "bar" | "line" | "pie" | "area" | "scatter" | "radar";

export interface ChartConfig {
  type: ChartType;
  xKey: string;
  yKeys: string[];
  title?: string;
}

interface ChartRendererProps {
  data: Record<string, unknown>[];
  config: ChartConfig;
}

const COLORS = [
  "hsl(221, 83%, 53%)",
  "hsl(160, 60%, 45%)",
  "hsl(38, 92%, 50%)",
  "hsl(0, 72%, 51%)",
  "hsl(271, 76%, 53%)",
  "hsl(190, 90%, 40%)",
  "hsl(330, 80%, 50%)",
  "hsl(100, 60%, 45%)",
];

const RechartsComponents = dynamic(
  () =>
    import("recharts").then((mod) => {
      const {
        ResponsiveContainer,
        BarChart,
        Bar,
        LineChart,
        Line,
        PieChart,
        Pie,
        Cell,
        AreaChart,
        Area,
        ScatterChart,
        Scatter,
        RadarChart,
        Radar,
        PolarGrid,
        PolarAngleAxis,
        PolarRadiusAxis,
        XAxis,
        YAxis,
        CartesianGrid,
        Tooltip,
        Legend,
      } = mod;

      function ChartInner({ data, config }: ChartRendererProps) {
        const { type, xKey, yKeys } = config;

        const numericData = useMemo(
          () =>
            data.map((row) => {
              const out: Record<string, unknown> = { ...row };
              for (const k of yKeys) {
                const v = row[k];
                if (typeof v === "string") {
                  const n = parseFloat(v.replace(",", "."));
                  if (!isNaN(n)) out[k] = n;
                }
              }
              return out;
            }),
          [data, yKeys],
        );

        if (type === "pie") {
          const pieData = numericData.map((row) => ({
            name: String(row[xKey] ?? ""),
            value: Number(row[yKeys[0]] ?? 0),
          }));

          return (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={(props) =>
                    `${props.name ?? ""} ${((Number(props.percent) || 0) * 100).toFixed(0)}%`
                  }
                  outerRadius={100}
                  dataKey="value"
                >
                  {pieData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          );
        }

        if (type === "radar") {
          return (
            <ResponsiveContainer width="100%" height={300}>
              <RadarChart data={numericData}>
                <PolarGrid />
                <PolarAngleAxis dataKey={xKey} />
                <PolarRadiusAxis />
                {yKeys.map((k, i) => (
                  <Radar
                    key={k}
                    name={k}
                    dataKey={k}
                    stroke={COLORS[i % COLORS.length]}
                    fill={COLORS[i % COLORS.length]}
                    fillOpacity={0.25}
                  />
                ))}
                <Tooltip />
                <Legend />
              </RadarChart>
            </ResponsiveContainer>
          );
        }

        if (type === "scatter") {
          return (
            <ResponsiveContainer width="100%" height={300}>
              <ScatterChart margin={{ top: 10, right: 20, bottom: 10, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey={xKey} name={xKey} type="number" />
                <YAxis dataKey={yKeys[0]} name={yKeys[0]} type="number" />
                <Tooltip cursor={{ strokeDasharray: "3 3" }} />
                <Legend />
                <Scatter
                  name={`${xKey} / ${yKeys[0]}`}
                  data={numericData}
                  fill={COLORS[0]}
                />
              </ScatterChart>
            </ResponsiveContainer>
          );
        }

        const ChartComponent = type === "area" ? AreaChart : type === "line" ? LineChart : BarChart;
        const SeriesComponent = type === "area" ? Area : type === "line" ? Line : Bar;

        return (
          <ResponsiveContainer width="100%" height={300}>
            <ChartComponent data={numericData} margin={{ top: 10, right: 20, bottom: 10, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey={xKey} tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              {yKeys.map((k, i) => {
                const color = COLORS[i % COLORS.length];
                if (type === "area") {
                  return (
                    <Area
                      key={k}
                      type="monotone"
                      dataKey={k}
                      stroke={color}
                      fill={color}
                      fillOpacity={0.3}
                    />
                  );
                }
                if (type === "line") {
                  return (
                    <Line
                      key={k}
                      type="monotone"
                      dataKey={k}
                      stroke={color}
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                  );
                }
                return <Bar key={k} dataKey={k} fill={color} />;
              })}
            </ChartComponent>
          </ResponsiveContainer>
        );
      }

      return ChartInner;
    }),
  { ssr: false, loading: () => <div className="h-[300px] flex items-center justify-center text-muted-foreground text-sm">Chargement du graphique...</div> },
);

export function ChartRenderer({ data, config }: ChartRendererProps) {
  if (!data?.length || !config?.xKey || !config?.yKeys?.length) {
    return null;
  }

  return (
    <div className="mt-3 rounded-lg border bg-background p-3">
      {config.title && (
        <p className="text-xs font-medium text-muted-foreground mb-2 truncate">
          {config.title}
        </p>
      )}
      <RechartsComponents data={data} config={config} />
    </div>
  );
}
