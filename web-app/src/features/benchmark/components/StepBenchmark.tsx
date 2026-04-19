import { useMemo, useState } from "react";
import { BarChart3, CheckCircle2, Copy, Gauge, Scale, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { useRecapStore } from "@/shared/storage/useRecapStore";

const metricRows = [
  { key: "panelCount", label: "Panel" },
  { key: "totalMs", label: "Total ms" },
  { key: "avgPanelMs", label: "Avg panel ms" },
  { key: "totalTokens", label: "Total tokens" },
  { key: "batchSizeUsed", label: "Batch size" },
  { key: "retryCount", label: "Retry" },
  { key: "rateLimitedCount", label: "429 count" },
  { key: "throttleWaitMs", label: "Throttle wait ms" },
] as const;

export function StepBenchmark() {
  const { benchmarkRecords, removeBenchmarkRecord } = useRecapStore();
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const selectedRecords = useMemo(
    () => benchmarkRecords.filter((record) => selectedIds.includes(record.id)),
    [benchmarkRecords, selectedIds]
  );

  const comparisonWinner = useMemo(() => {
    if (selectedRecords.length !== 2) return null;
    const [left, right] = selectedRecords;
    if (left.overallScore === right.overallScore) return null;
    return left.overallScore > right.overallScore ? left : right;
  }, [selectedRecords]);

  const toggleSelected = (id: string) => {
    setSelectedIds((current) => {
      if (current.includes(id)) return current.filter((item) => item !== id);
      if (current.length >= 2) return [current[1], id];
      return [...current, id];
    });
  };

  if (benchmarkRecords.length === 0) {
    return (
      <div className="flex h-[65vh] flex-col items-center justify-center gap-4 text-center">
        <div className="rounded-full border border-white/10 bg-white/5 p-5">
          <BarChart3 className="h-8 w-8 text-primary" />
        </div>
        <div className="space-y-2">
          <h2 className="text-2xl font-bold text-white">Chưa có benchmark record</h2>
          <p className="max-w-xl text-sm text-white/60">
            Sau khi generate script ở tab Kịch Bản, bấm Save benchmark để lưu voiceover và metrics vào đây.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-1">
          <h2 className="text-3xl font-bold tracking-tight text-white">Benchmark Lab</h2>
          <p className="text-sm text-white/65">
            Chọn tối đa 2 bản ghi để so sánh điểm, latency, token và độ ổn định của script generation.
          </p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white/70">
          Đang lưu {benchmarkRecords.length} record
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1.05fr_0.95fr]">
        <div className="space-y-4">
          {benchmarkRecords.map((record) => {
            const selected = selectedIds.includes(record.id);
            return (
              <Card
                key={record.id}
                className={`glass animate-in slide-in-from-bottom flex-1 rounded-3xl border p-6 transition-all duration-300 ${
                  selected ? "border-primary/45 bg-primary/10 shadow-glow" : "border-white/10 bg-white/5 shadow-2xl hover:border-white/20"
                }`}
              >
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="space-y-3">
                    <div className="flex items-center gap-3">
                      <div className="rounded-2xl border border-white/10 bg-black/20 px-3 py-2 text-sm font-semibold text-white">
                        {record.grade}
                      </div>
                      <div>
                        <h3 className="text-base font-semibold text-white">{record.title}</h3>
                        <p className="text-xs text-white/50">{new Date(record.createdAt).toLocaleString()}</p>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2 text-xs text-white/70">
                      <span className="rounded-full border border-white/10 bg-black/20 px-3 py-1">
                        Score {record.overallScore}
                      </span>
                      <span className="rounded-full border border-white/10 bg-black/20 px-3 py-1">
                        {record.panelCount} panel
                      </span>
                      <span className="rounded-full border border-white/10 bg-black/20 px-3 py-1">
                        Avg {Math.round(record.metrics.avgPanelMs)} ms/panel
                      </span>
                    </div>
                    <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                      {record.dimensionScores.map((item) => (
                        <div key={item.key} className="rounded-2xl border border-white/10 bg-black/20 px-3 py-3">
                          <div className="flex items-center justify-between gap-3">
                            <span className="text-xs font-semibold uppercase tracking-wide text-white/55">{item.label}</span>
                            <span className="text-sm font-bold text-white">{item.score}</span>
                          </div>
                          <p className="mt-2 text-xs leading-5 text-white/55">{item.note}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <Button
                      variant={selected ? "default" : "outline"}
                      onClick={() => toggleSelected(record.id)}
                      className="rounded-xl"
                    >
                      <Scale className="mr-2 h-4 w-4" />
                      {selected ? "Bỏ chọn" : "So sánh"}
                    </Button>
                    <Button
                      variant="outline"
                      onClick={async () => {
                        await navigator.clipboard.writeText(record.combinedText);
                        setCopiedId(record.id);
                        window.setTimeout(() => setCopiedId(null), 2000);
                      }}
                      className="rounded-xl"
                    >
                      {copiedId === record.id ? <CheckCircle2 className="mr-2 h-4 w-4" /> : <Copy className="mr-2 h-4 w-4" />}
                      Copy
                    </Button>
                    <Button variant="outline" onClick={() => removeBenchmarkRecord(record.id)} className="rounded-xl border-red-500/25 bg-red-500/10 text-red-100 hover:bg-red-500/15">
                      <Trash2 className="mr-2 h-4 w-4" />
                      Xóa
                    </Button>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>

        <div className="space-y-4">
          <Card className="glass rounded-3xl border border-white/10 bg-white/5 p-6 shadow-2xl transition-all duration-300">
            <div className="flex items-center gap-3">
              <div className="rounded-2xl border border-white/10 bg-black/20 p-3">
                <Gauge className="h-5 w-5 text-primary" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-white">Comparison Result</h3>
                <p className="text-sm text-white/55">Cần 2 record được chọn để mở bảng so sánh chi tiết.</p>
              </div>
            </div>

            {selectedRecords.length !== 2 ? (
              <div className="mt-5 rounded-2xl border border-dashed border-white/10 bg-black/20 p-5 text-sm text-white/55">
                Đang chọn {selectedRecords.length}/2 record.
              </div>
            ) : (
              <div className="mt-5 space-y-5">
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                  {comparisonWinner ? (
                    <p className="text-sm leading-6 text-white">
                      <span className="font-semibold text-primary">{comparisonWinner.title}</span> đang dẫn trước với
                      score tổng {comparisonWinner.overallScore}.
                    </p>
                  ) : (
                    <p className="text-sm leading-6 text-white">Hai record đang hòa điểm tổng.</p>
                  )}
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <div />
                  {selectedRecords.map((record) => (
                    <div key={record.id} className="rounded-2xl border border-white/10 bg-black/20 p-4">
                      <p className="text-sm font-semibold text-white">{record.title}</p>
                      <p className="mt-1 text-xs text-white/50">{record.overallScore} điểm</p>
                    </div>
                  ))}
                </div>

                {selectedRecords[0].dimensionScores.map((dimension, index) => {
                  const left = selectedRecords[0].dimensionScores[index];
                  const right = selectedRecords[1].dimensionScores[index];
                  const leftBetter = left.score > right.score;
                  const rightBetter = right.score > left.score;

                  return (
                    <div key={dimension.key} className="grid grid-cols-3 gap-3">
                      <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                        <p className="text-xs font-semibold uppercase tracking-wide text-white/55">{dimension.label}</p>
                      </div>
                      <div className={`rounded-2xl border p-4 ${leftBetter ? "border-emerald-500/30 bg-emerald-500/10" : "border-white/10 bg-black/20"}`}>
                        <p className="text-sm font-semibold text-white">{left.score}</p>
                        <p className="mt-1 text-xs text-white/55">{left.note}</p>
                      </div>
                      <div className={`rounded-2xl border p-4 ${rightBetter ? "border-emerald-500/30 bg-emerald-500/10" : "border-white/10 bg-black/20"}`}>
                        <p className="text-sm font-semibold text-white">{right.score}</p>
                        <p className="mt-1 text-xs text-white/55">{right.note}</p>
                      </div>
                    </div>
                  );
                })}

                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  {metricRows.map((row) => (
                    <div key={row.key} className="rounded-2xl border border-white/10 bg-black/20 p-4">
                      <p className="text-xs font-semibold uppercase tracking-wide text-white/55">{row.label}</p>
                      <div className="mt-2 flex items-center justify-between gap-4 text-sm text-white">
                        <span>{String(selectedRecords[0].metrics[row.key])}</span>
                        <span className="text-white/35">vs</span>
                        <span>{String(selectedRecords[1].metrics[row.key])}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Card>

          {selectedRecords[0] && (
            <Card className="glass mt-4 animate-in slide-in-from-bottom rounded-3xl border border-white/10 bg-white/5 p-6 shadow-2xl">
              <h3 className="text-base font-semibold text-white">Merged Benchmark Text</h3>
              <p className="mt-1 text-sm text-white/55">
                Voiceover đã được ghép liền mạch và nối thêm log completion + metrics.
              </p>
              <Textarea
                readOnly
                value={selectedRecords[0].combinedText}
                className="mt-4 min-h-[260px] rounded-2xl border-white/10 bg-black/30 font-mono text-xs leading-6 text-white/75"
              />
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
