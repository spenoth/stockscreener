import { CommonModule } from '@angular/common';
import { Component, Input, OnChanges } from '@angular/core';
import { BaseChartDirective } from 'ng2-charts';
import { ChartData, ChartDataset, ChartOptions, Point } from 'chart.js';
import { SupertrendPath } from '../../models/stock.model';

type ClassificationMode = 'endpoint' | 'mean';

@Component({
  selector: 'app-supertrend-paths-chart',
  standalone: true,
  imports: [CommonModule, BaseChartDirective],
  templateUrl: './supertrend-paths-chart.component.html',
  styleUrls: ['./supertrend-paths-chart.component.css']
})
export class SupertrendPathsChartComponent implements OnChanges {
  @Input() ticker = '';
  @Input() timeframe = '1h';
  @Input() paths: SupertrendPath[] = [];

  endpointChartData: ChartData<'line', Point[]> = { datasets: [] };
  meanChartData: ChartData<'line', Point[]> = { datasets: [] };

  endpointChartOptions: ChartOptions<'line'> = {};
  meanChartOptions: ChartOptions<'line'> = {};

  ngOnChanges(): void {
    this.rebuildCharts();
  }

  get totalCount(): number {
    return this.paths.length;
  }

  get endpointPositiveCount(): number {
    return this.paths.filter(path => path.endpoint_positive).length;
  }

  get endpointNegativeCount(): number {
    return this.totalCount - this.endpointPositiveCount;
  }

  get meanPositiveCount(): number {
    return this.paths.filter(path => path.mean_positive).length;
  }

  get meanNegativeCount(): number {
    return this.totalCount - this.meanPositiveCount;
  }

  private rebuildCharts(): void {
    const yBounds = this.calculateSharedYBounds();

    this.endpointChartData = {
      datasets: this.buildDatasets('endpoint')
    };

    this.meanChartData = {
      datasets: this.buildDatasets('mean')
    };

    this.endpointChartOptions = this.buildOptions('By Endpoint (last value)', yBounds);
    this.meanChartOptions = this.buildOptions('By Mean (mostly above or below entry)', yBounds);
  }

  private buildDatasets(mode: ClassificationMode): ChartDataset<'line', Point[]>[] {
    const pathDatasets = this.paths.map((entry, index) => {
      const positive = mode === 'endpoint' ? entry.endpoint_positive : entry.mean_positive;
      const color = positive ? 'rgba(0, 128, 0, 0.3)' : 'rgba(220, 0, 0, 0.3)';
      const values = this.getChartPath(entry);

      return {
        label: `Signal ${index + 1}`,
        data: values.map((value, hour) => ({ x: hour, y: value })),
        borderColor: color,
        backgroundColor: 'transparent',
        borderWidth: 1,
        pointRadius: 0,
        pointHoverRadius: 0,
        tension: 0,
        fill: false
      } satisfies ChartDataset<'line', Point[]>;
    });

    return [...pathDatasets, this.buildZeroLineDataset()];
  }

  private buildZeroLineDataset(): ChartDataset<'line', Point[]> {
    const maxHours = Math.max(0, ...this.paths.map(entry => this.getChartPath(entry).length - 1));

    return {
      label: 'Zero line',
      data: [
        { x: 0, y: 0 },
        { x: maxHours, y: 0 }
      ],
      borderColor: 'rgba(120, 120, 120, 0.9)',
      borderWidth: 1,
      borderDash: [6, 4],
      pointRadius: 0,
      pointHoverRadius: 0,
      tension: 0,
      fill: false
    };
  }

  private buildOptions(title: string, yBounds: { min: number; max: number }): ChartOptions<'line'> {
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      parsing: false,
      normalized: true,
      interaction: {
        mode: 'nearest',
        intersect: false
      },
      plugins: {
        title: {
          display: true,
          text: title,
          font: {
            size: 16
          }
        },
        legend: {
          display: false
        },
        tooltip: {
          callbacks: {
            title: items => {
              const hour = items[0]?.parsed.x ?? 0;
              return `Hours since signal: ${hour}`;
            },
            label: item => `% change: ${item.parsed.y.toFixed(2)}%`
          }
        }
      },
      scales: {
        x: {
          type: 'linear',
          title: {
            display: true,
            text: 'Hours since signal'
          },
          ticks: {
            precision: 0
          },
          grid: {
            display: true
          }
        },
        y: {
          min: yBounds.min,
          max: yBounds.max,
          title: {
            display: true,
            text: '% change'
          },
          grid: {
            display: true
          }
        }
      }
    };
  }

  private calculateSharedYBounds(): { min: number; max: number } {
    const values = this.paths.flatMap(entry => this.getChartPath(entry));

    if (values.length === 0) {
      return { min: -5, max: 5 };
    }

    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = Math.max((max - min) * 0.1, 1);

    return {
      min: Math.floor(min - padding),
      max: Math.ceil(max + padding)
    };
  }

  private getChartPath(entry: SupertrendPath): number[] {
    return entry.path_percent?.length ? entry.path_percent : entry.path;
  }
}

