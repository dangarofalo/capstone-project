import { useEffect, useMemo, useState } from "react";
import { BarElement, CategoryScale, Chart as ChartJS, LinearScale, Tooltip } from "chart.js";
import { Bar } from "react-chartjs-2";
import { bucketLabel, formatNumber } from "../lib/format.js";

ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip);

// Three series in a fixed order (validated colorblind-safe). The rarer account-change
// events are folded into "Account changes" so the chart never needs more than three hues.
const SERIES = [
  { key: "success", label: "Successful logins", color: "--sv-series-1", types: ["login_success"] },
  { key: "failure", label: "Failed logins", color: "--sv-series-2", types: ["login_failure"] },
  {
    key: "other",
    label: "Account changes & lockouts",
    color: "--sv-series-3",
    types: ["account_lockout", "account_created", "admin_group_added"],
  },
];

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

// Re-read the CSS colors when the system switches between light and dark mode.
function useColorScheme() {
  const query = "(prefers-color-scheme: dark)";
  const [dark, setDark] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const update = () => setDark(mq.matches);
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  return dark;
}

export default function EventsChart({ timeline }) {
  const dark = useColorScheme();
  const [showTable, setShowTable] = useState(false);

  const rows = useMemo(
    () =>
      timeline.labels.map((label, i) => {
        const row = { label: bucketLabel(label, timeline.bucket), start: label };
        for (const s of SERIES) row[s.key] = s.types.reduce((sum, t) => sum + (timeline.series[t]?.[i] || 0), 0);
        return row;
      }),
    [timeline],
  );

  const { data, options } = useMemo(() => {
    const surface = cssVar("--sv-surface");
    const muted = cssVar("--sv-muted");
    const grid = cssVar("--sv-line");
    return {
      data: {
        labels: rows.map((r) => r.label),
        datasets: SERIES.map((s) => ({
          label: s.label,
          data: rows.map((r) => r[s.key]),
          backgroundColor: cssVar(s.color),
          // A 2px surface-colored edge separates stacked segments.
          borderColor: surface,
          borderWidth: { top: 2 },
          borderRadius: 2,
          borderSkipped: "start",
          maxBarThickness: 28,
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        interaction: { mode: "index", intersect: false },
        scales: {
          x: {
            stacked: true,
            grid: { display: false },
            border: { color: cssVar("--sv-line-strong") },
            ticks: { color: muted, maxRotation: 0, autoSkip: true, autoSkipPadding: 12 },
          },
          y: {
            stacked: true,
            beginAtZero: true,
            grid: { color: grid },
            border: { display: false },
            ticks: { color: muted, precision: 0 },
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: cssVar("--sv-raised"),
            titleColor: cssVar("--sv-ink"),
            bodyColor: cssVar("--sv-ink-2"),
            borderColor: grid,
            borderWidth: 1,
            padding: 10,
            boxPadding: 4,
            usePointStyle: true,
            callbacks: {
              title: (items) => new Date(rows[items[0].dataIndex].start).toLocaleString(undefined, {
                weekday: "short", month: "short", day: "numeric",
                ...(timeline.bucket === "hour" ? { hour: "numeric" } : {}),
              }),
              label: (item) => ` ${item.dataset.label}: ${formatNumber(item.raw)}`,
            },
          },
        },
      },
    };
    // dark is a dependency so colors are re-read after a theme change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, timeline.bucket, dark]);

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink-2" aria-label="Legend">
          {SERIES.map((s) => (
            <li key={s.key} className="flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: `var(${s.color})` }} />
              {s.label}
            </li>
          ))}
        </ul>
        <button type="button" className="text-sm text-accent hover:underline" onClick={() => setShowTable((v) => !v)}>
          {showTable ? "Show chart" : "View as table"}
        </button>
      </div>
      {showTable ? (
        <div className="max-h-72 overflow-auto rounded-md border border-line">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-raised text-left text-ink-2">
              <tr>
                <th className="px-3 py-2 font-medium">{timeline.bucket === "hour" ? "Hour" : "Day"}</th>
                {SERIES.map((s) => (
                  <th key={s.key} className="px-3 py-2 text-right font-medium">{s.label}</th>
                ))}
              </tr>
            </thead>
            <tbody className="tabular">
              {rows.map((r) => (
                <tr key={r.start} className="border-t border-line">
                  <td className="px-3 py-1.5">{new Date(r.start).toLocaleString(undefined, { month: "short", day: "numeric", ...(timeline.bucket === "hour" ? { hour: "numeric" } : {}) })}</td>
                  {SERIES.map((s) => (
                    <td key={s.key} className="px-3 py-1.5 text-right">{formatNumber(r[s.key])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="h-64" role="img" aria-label="Security events over time, stacked by type. Use 'View as table' for the numbers.">
          <Bar data={data} options={options} />
        </div>
      )}
    </div>
  );
}
