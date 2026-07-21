import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { ScreenerService } from './screener.service';
import { Stock } from '../models/stock.model';

describe('ScreenerService', () => {
  let service: ScreenerService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule]
    });
    service = TestBed.inject(ScreenerService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should call the correct URL', () => {
    service.getCurrentStocks().subscribe();
    const req = httpMock.expectOne('http://localhost:8000/api/screener/bmsb/current');
    expect(req.request.method).toBe('GET');
    req.flush([]);
  });

  it('should return typed Stock array', () => {
    const mockStocks: Stock[] = [
      { symbol: 'AAPL', exchange: 'NASDAQ' },
      { symbol: 'MSFT', exchange: 'NASDAQ' }
    ];

    service.getCurrentStocks().subscribe(stocks => {
      expect(stocks.length).toBe(2);
      expect(stocks[0].symbol).toBe('AAPL');
      expect(stocks[0].exchange).toBe('NASDAQ');
    });

    const req = httpMock.expectOne('http://localhost:8000/api/screener/bmsb/current');
    req.flush(mockStocks);
  });

  it('should handle empty array response without error', () => {
    service.getCurrentStocks().subscribe(stocks => {
      expect(stocks).toEqual([]);
      expect(stocks.length).toBe(0);
    });

    const req = httpMock.expectOne('http://localhost:8000/api/screener/bmsb/current');
    req.flush([]);
  });

  it('should call the BMSB SuperTrend analysis endpoint with an encoded symbol', () => {
    service.getBmsbSupertrendAnalysis('BRK.B').subscribe(response => {
      expect(response.paths).toEqual([]);
    });

    const req = httpMock.expectOne('http://localhost:8000/api/analysis/bmsb-supertrend/BRK.B');
    expect(req.request.method).toBe('GET');
    req.flush({ paths: [] });
  });
});
