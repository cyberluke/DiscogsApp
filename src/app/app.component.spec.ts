import { ComponentFixture, TestBed } from '@angular/core/testing';
import { RouterModule } from '@angular/router';
import { AppComponent } from './app.component';

describe('AppComponent', () => {
  let fixture: ComponentFixture<AppComponent>;

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [AppComponent],
      imports: [RouterModule.forRoot([])]
    });

    fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
  });

  it('renders primary navigation links', () => {
    const text = fixture.nativeElement.textContent;

    expect(text).toContain('Library');
    expect(text).toContain('Now Playing');
  });
});