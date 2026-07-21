import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { catchError, distinctUntilChanged, filter, finalize, map, of, switchMap } from 'rxjs';
import { ScreenerService } from '../../services/screener.service';
import { SupertrendAnalysisResponse } from '../../models/stock.model';
import { SupertrendPathsChartComponent } from '../supertrend-paths-chart/supertrend-paths-chart.component';

@Component({
  selector: 'app-analyze-page',
  standalone: true,
  imports: [CommonModule, RouterLink, SupertrendPathsChartComponent],
  templateUrl: './analyze-page.component.html',
  styleUrls: ['./analyze-page.component.css']
})
export class AnalyzePageComponent implements OnInit {
  ticker = '';
  timeframe = '1h';
  loading = false;
  error = false;
  analysis?: SupertrendAnalysisResponse;

  constructor(
    private route: ActivatedRoute,
    private screenerService: ScreenerService
  ) {}

  ngOnInit(): void {
    this.route.paramMap
      .pipe(
        map(params => params.get('ticker')?.trim().toUpperCase() ?? ''),
        filter(ticker => ticker.length > 0),
        distinctUntilChanged(),
        switchMap(ticker => {
          this.ticker = ticker;
          this.loading = true;
          this.error = false;
          this.analysis = undefined;

          return this.screenerService.getBmsbSupertrendAnalysis(ticker).pipe(
            catchError(() => {
              this.error = true;
              return of(undefined);
            }),
            finalize(() => {
              this.loading = false;
            })
          );
        })
      )
      .subscribe(response => {
        this.analysis = response;
      });
  }
}

