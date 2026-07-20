import { render, screen } from '@testing-library/react';
import { SafeMarkdownText } from '../src/components/chat/SafeMarkdownText';

describe('SafeMarkdownText', () => {
  it('renders model bold and code markers without exposing literal syntax', () => {
    render(<SafeMarkdownText text={'**December 2023:** peak in `payment_count`.'} />);

    expect(screen.getByText('December 2023:').tagName).toBe('STRONG');
    expect(screen.getByText('payment_count').tagName).toBe('CODE');
    expect(screen.queryByText(/\*\*/)).not.toBeInTheDocument();
  });

  it('renders bullet lines as safe text rather than HTML', () => {
    render(<SafeMarkdownText text={'- First finding\n- <script>alert(1)</script>'} />);

    expect(screen.getByText('First finding')).toBeInTheDocument();
    expect(screen.getByText('<script>alert(1)</script>')).toBeInTheDocument();
    expect(document.querySelector('script')).toBeNull();
  });
});
