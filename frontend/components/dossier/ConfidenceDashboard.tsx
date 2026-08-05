"use client";

import { CircularProgressbar, buildStyles } from "react-circular-progressbar";
import "react-circular-progressbar/dist/styles.css";
import { RadialBarChart, RadialBar, Legend, ResponsiveContainer, PolarAngleAxis } from "recharts";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ConfidenceBreakdown } from "@/src/lib/types";
import {
  formatPercent,
  getConfidenceColor,
  getConfidenceProgressColor,
  getConfidenceBadgeVariant,
} from "@/src/lib/utils";
import { cn } from "@/src/lib/utils";

interface ConfidenceDashboardProps {
  confidence: ConfidenceBreakdown[];
  className?: string;
}

function getProgressColor(score: number): string {
  if (score >= 0.9) return "#10b981"; // green-500
  if (score >= 0.7) return "#f59e0b"; // amber-500
  return "#f97316"; // orange-500
}

export function ConfidenceDashboard({ confidence, className }: ConfidenceDashboardProps) {
  if (!confidence || confidence.length === 0) {
    return null;
  }

  // Calculate overall confidence (average of all scores)
  const overallConfidence =
    confidence.reduce((sum, item) => sum + item.score, 0) / confidence.length;

  // Prepare data for Recharts radial bar
  const chartData = confidence.map((item, index) => ({
    name: item.label,
    value: item.score * 100,
    fill: getProgressColor(item.score),
  }));

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>Confidence Analysis</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Overall Confidence Circle */}
          <div className="flex flex-col items-center">
            <div className="w-32 h-32 mb-3">
              <CircularProgressbar
                value={overallConfidence * 100}
                text={`${Math.round(overallConfidence * 100)}%`}
                styles={buildStyles({
                  textSize: "24px",
                  pathColor: getProgressColor(overallConfidence),
                  textColor: "currentColor",
                  trailColor: "rgba(0, 0, 0, 0.1)",
                })}
              />
            </div>
            <p className="text-sm font-medium text-muted-foreground">Overall Match Confidence</p>
          </div>

          {/* Radial Bar Chart */}
          <div className="flex flex-col items-center">
            <ResponsiveContainer width="100%" height={200}>
              <RadialBarChart
                cx="50%"
                cy="50%"
                innerRadius="20%"
                outerRadius="90%"
                data={chartData}
                startAngle={90}
                endAngle={-270}
              >
                <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
                <RadialBar background dataKey="value" cornerRadius={10} />
              </RadialBarChart>
            </ResponsiveContainer>
            <p className="text-xs text-muted-foreground text-center mt-2">Category Breakdown</p>
          </div>
        </div>

        {/* Confidence Breakdown */}
        <div className="space-y-4">
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Breakdown by Category
          </p>
          {confidence.map((item) => (
            <div key={item.label} className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">{item.label}</span>
                <div className="flex items-center gap-2">
                  <span className={cn("text-sm font-bold", getConfidenceColor(item.score))}>
                    {formatPercent(item.score)}
                  </span>
                  <Badge variant={getConfidenceBadgeVariant(item.score)} className="text-xs">
                    {item.score >= 0.9 ? "High" : item.score >= 0.7 ? "Medium" : "Low"}
                  </Badge>
                </div>
              </div>

              {/* Progress bar */}
              <div className="relative h-2 w-full overflow-hidden rounded-full bg-secondary">
                <div
                  className={cn(
                    "absolute top-0 left-0 h-full rounded-full transition-all",
                    getConfidenceProgressColor(item.score),
                  )}
                  style={{ width: `${item.score * 100}%` }}
                />
              </div>

              {/* Evidence chips */}
              {item.evidence && item.evidence.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {item.evidence.map((evidence, idx) => (
                    <span
                      key={idx}
                      className="inline-flex items-center rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground"
                    >
                      {evidence}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
