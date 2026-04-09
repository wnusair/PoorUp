import { fireEvent, render, screen } from '@testing-library/react';
import HelpTooltip from './HelpTooltip';


describe('HelpTooltip', () => {
  it('previews on hover and stays open only when pinned', () => {
    render(<HelpTooltip content="Cash bonuses reward money you keep on hand." label="Cash bonus help" />);

    const button = screen.getByRole('button', { name: 'Cash bonus help' });

    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();

    fireEvent.mouseEnter(button);
    expect(screen.getByRole('tooltip')).toHaveTextContent('Cash bonuses reward money you keep on hand.');

    fireEvent.mouseLeave(button);
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();

    fireEvent.click(button);
    expect(screen.getByRole('tooltip')).toBeInTheDocument();

    fireEvent.mouseLeave(button);
    expect(screen.getByRole('tooltip')).toBeInTheDocument();

    fireEvent.keyDown(button, { key: 'Escape' });
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });
});
