import { Component, ElementRef, ViewChild, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';

interface PathEntry {
  path: number[];
  endpoint_positive: boolean;
  mean_positive: boolean;
}

interface BmsbSupertrendResponse {
  stats: {
    total_signals: number;
    bmsb_above: number;
    bmsb_below_or_unknown: number;
  };
  paths: PathEntry[];
  metrics: any[];
  summary: Record<string, any>;
  drawdown_percentiles: Record<string, number>;
  mean_path: number[];
}

@Component({
  selector: 'app-bmsb-supertrend',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './bmsb-supertrend.component.html',
  styleUrls: ['./bmsb-supertrend.component.css'],
})
export class BmsbSupertrendComponent implements OnDestroy {
  @ViewChild('endpointCanvas') endpointCanvasRef!: ElementRef<HTMLCanvasElement>;
  @ViewChild('meanCanvas') meanCanvasRef!: ElementRef<HTMLCanvasElement>;

  symbol = 'TSLA';
  loading = false;
  error: string | null = null;

  data: BmsbSupertrendResponse | null = null;

  constructor(private http: HttpClient) {}

  ngOnDestroy() {}

  analyze() {
    this.loading = true;
    this.error = null;
    this.data = null;

    this.http
      .get<BmsbSupertrendResponse>(
        `${environment.apiBaseUrl}/api/analysis/bmsb-supertrend/${this.symbol.toUpperCase()}`
      )
      .subscribe({
        next: (res) => {
          this.data = res;
          this.loading = false;
          setTimeout(() => this.drawCharts(), 0);
        },
        error: (err) => {
          this.error = err.error?.detail || 'Failed to fetch analysis data';
          this.loading = false;
        },
      });
  }

  private drawCharts() {
    if (!this.data) return;
    this.drawChart(this.endpointCanvasRef.nativeElement, this.data.paths, 'endpoint_positive', 'By Endpoint (last value)');
    this.drawChart(this.meanCanvasRef.nativeElement, this.data.paths, 'mean_positive', 'By Mean (mostly above or below entry)');
  }

  private drawChart(
    canvas: HTMLCanvasElement,
    paths: PathEntry[],
    colorKey: 'endpoint_positive' | 'mean_positive',
    title: string
  ) {
    const ctx = canvas.getContext('2d')!;
    const width = canvas.width;
    const height = canvas.height;
    const padding = { top: 40, bottom: 40, left: 60, right: 20 };

    ctx.clearRect(0, 0, width, height);

    if (!paths.length) return;

    // Determine Y range
    let yMin = 0, yMax = 0;
    for (const p of paths) {
      for (const v of p.path) {
        if (v < yMin) yMin = v;
        if (v > yMax) yMax = v;
      }
    }
    const yMargin = (yMax - yMin) * 0.1 || 1;
    yMin -= yMargin;
    yMax += yMargin;

    const maxLen = Math.max(...paths.map(p => p.path.length));

    const plotW = width - padding.left - padding.right;
    const plotH = height - padding.top - padding.bottom;

    const xScale = (i: number) => padding.left + (i / (maxLen - 1)) * plotW;
    const yScale = (v: number) => padding.top + plotH - ((v - yMin) / (yMax - yMin)) * plotH;

    // Draw grid
    ctx.strokeStyle = '#e0e0e0';
    ctx.lineWidth = 1;
    const yTicks = 5;
    for (let i = 0; i <= yTicks; i++) {
      const y = padding.top + (i / yTicks) * plotH;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();
      const val = yMax - (i / yTicks) * (yMax - yMin);
      ctx.fillStyle = '#666';
      ctx.font = '11px sans-serif';
      ctx.textAlign = 'right';
      ctx.fillText(val.toFixed(2) + '%', padding.left - 5, y + 4);
    }

    // Zero line
    ctx.strokeStyle = '#999';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([5, 3]);
    ctx.beginPath();
    ctx.moveTo(padding.left, yScale(0));
    ctx.lineTo(width - padding.right, yScale(0));
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw paths
    ctx.lineWidth = 0.8;
    ctx.globalAlpha = 0.3;

    const nPos = paths.filter(p => p[colorKey]).length;
    const nNeg = paths.length - nPos;

    for (const entry of paths) {
      ctx.strokeStyle = entry[colorKey] ? '#4caf50' : '#f44336';
      ctx.beginPath();
      for (let i = 0; i < entry.path.length; i++) {
        const x = xScale(i);
        const y = yScale(entry.path[i]);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }

    ctx.globalAlpha = 1.0;

    // Draw mean path
    if (this.data?.mean_path?.length) {
      ctx.strokeStyle = '#1565c0';
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      for (let i = 0; i < this.data.mean_path.length; i++) {
        const x = xScale(i);
        const y = yScale(this.data.mean_path[i]);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }

    // Title
    ctx.fillStyle = '#333';
    ctx.font = 'bold 14px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(title, width / 2, 20);

    // X label
    ctx.font = '11px sans-serif';
    ctx.fillText('Hours since signal', width / 2, height - 5);

    // Legend
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'left';
    ctx.fillStyle = '#4caf50';
    ctx.fillRect(padding.left + 10, padding.top + 5, 12, 12);
    ctx.fillStyle = '#333';
    ctx.fillText(`Positive (${nPos})`, padding.left + 26, padding.top + 15);
    ctx.fillStyle = '#f44336';
    ctx.fillRect(padding.left + 10, padding.top + 22, 12, 12);
    ctx.fillStyle = '#333';
    ctx.fillText(`Negative (${nNeg})`, padding.left + 26, padding.top + 32);
  }
}

