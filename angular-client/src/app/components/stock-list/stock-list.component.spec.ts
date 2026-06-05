import { ComponentFixture, TestBed } from '@angular/core/testing';
import { StockListComponent } from './stock-list.component';
import { ScreenerService } from '../../services/screener.service';
import { of, throwError, NEVER } from 'rxjs';
import { Stock } from '../../models/stock.model';

describe('StockListComponent', () => {
  let component: StockListComponent;
  let fixture: ComponentFixture<StockListComponent>;
  let mockScreenerService: jasmine.SpyObj<ScreenerService>;

  beforeEach(async () => {
    mockScreenerService = jasmine.createSpyObj('ScreenerService', ['getCurrentStocks']);
    // Default to never-emitting observable so loading state is testable
    mockScreenerService.getCurrentStocks.and.returnValue(of([]));

    await TestBed.configureTestingModule({
      imports: [StockListComponent],
      providers: [
        { provide: ScreenerService, useValue: mockScreenerService }
      ]
    }).compileComponents();
  });

  function createComponent(): void {
    fixture = TestBed.createComponent(StockListComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  }

  it('should create', () => {
    createComponent();
    expect(component).toBeTruthy();
  });

  it('should show loading state before data arrives', () => {
    // Don't call createComponent yet — set up a pending observable that never emits
    mockScreenerService.getCurrentStocks.and.returnValue(NEVER);

    fixture = TestBed.createComponent(StockListComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();

    const el: HTMLElement = fixture.nativeElement;
    expect(el.querySelector('[data-testid="loading"]')).toBeTruthy();
    expect(el.querySelector('[data-testid="stock-table"]')).toBeNull();
    expect(el.querySelector('[data-testid="empty"]')).toBeNull();
    expect(el.querySelector('[data-testid="error"]')).toBeNull();
  });

  it('should render stock data when service returns results', () => {
    const stocks: Stock[] = [
      { symbol: 'AAPL', exchange: 'NASDAQ' },
      { symbol: 'IBM', exchange: 'NYSE' }
    ];
    mockScreenerService.getCurrentStocks.and.returnValue(of(stocks));
    createComponent();

    const el: HTMLElement = fixture.nativeElement;
    expect(el.querySelector('[data-testid="stock-table"]')).toBeTruthy();
    expect(el.querySelector('[data-testid="loading"]')).toBeNull();
    const rows = el.querySelectorAll('tbody tr');
    expect(rows.length).toBe(2);
    expect(rows[0].textContent).toContain('AAPL');
    expect(rows[0].textContent).toContain('NASDAQ');
  });

  it('should show empty-state message when service returns empty array', () => {
    mockScreenerService.getCurrentStocks.and.returnValue(of([]));
    createComponent();

    const el: HTMLElement = fixture.nativeElement;
    expect(el.querySelector('[data-testid="empty"]')).toBeTruthy();
    expect(el.querySelector('[data-testid="stock-table"]')).toBeNull();
    expect(el.querySelector('[data-testid="error"]')).toBeNull();
    expect(el.querySelector('[data-testid="loading"]')).toBeNull();
  });

  it('should show error state when service call fails', () => {
    mockScreenerService.getCurrentStocks.and.returnValue(throwError(() => new Error('fail')));
    createComponent();

    const el: HTMLElement = fixture.nativeElement;
    expect(el.querySelector('[data-testid="error"]')).toBeTruthy();
    expect(el.querySelector('[data-testid="stock-table"]')).toBeNull();
    expect(el.querySelector('[data-testid="empty"]')).toBeNull();
  });

  it('should generate correct TradingView URL', () => {
    const stocks: Stock[] = [{ symbol: 'TSLA', exchange: 'NASDAQ' }];
    mockScreenerService.getCurrentStocks.and.returnValue(of(stocks));
    createComponent();

    const link = fixture.nativeElement.querySelector('a[target="_blank"]') as HTMLAnchorElement;
    expect(link).toBeTruthy();
    expect(link.href).toBe('https://www.tradingview.com/chart/?symbol=NASDAQ:TSLA');
    expect(link.rel).toBe('noopener noreferrer');
  });

  it('should not render TradingView link when exchange is null or empty', () => {
    const stocks: Stock[] = [
      { symbol: 'XYZ', exchange: '' },
      { symbol: 'ABC', exchange: null as any }
    ];
    mockScreenerService.getCurrentStocks.and.returnValue(of(stocks));
    createComponent();

    const links = fixture.nativeElement.querySelectorAll('a[target="_blank"]');
    expect(links.length).toBe(0);

    const rows = fixture.nativeElement.querySelectorAll('tbody tr');
    expect(rows.length).toBe(2);
  });
});

