import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Stock, SupertrendAnalysisResponse } from '../models/stock.model';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class ScreenerService {
  private readonly apiUrl = `${environment.apiBaseUrl}/api/screener/bmsb/current`;
  private readonly retrieverUrl = `${environment.apiBaseUrl}/api/retriever/prices`;
  private readonly analysisUrl = `${environment.apiBaseUrl}/api/analysis/bmsb-supertrend`;

  constructor(private http: HttpClient) {}

  getCurrentStocks(): Observable<Stock[]> {
    return this.http.get<Stock[]>(this.apiUrl);
  }

  getBmsbSupertrendAnalysis(symbol: string): Observable<SupertrendAnalysisResponse> {
    return this.http.get<SupertrendAnalysisResponse>(
      `${this.analysisUrl}/${encodeURIComponent(symbol)}`
    );
  }

  loadHistoricalPrices(symbol: string, timeframe: string): Observable<{ symbol: string; timeframe: string; inserted: number }> {
    return this.http.get<{ symbol: string; timeframe: string; inserted: number }>(
      `${this.retrieverUrl}/${symbol}/${timeframe}`
    );
  }
}
