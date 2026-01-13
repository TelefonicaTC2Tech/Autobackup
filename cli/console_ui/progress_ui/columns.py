from rich.progress import SpinnerColumn, Task
from rich.console import RenderableType


class SpinnerCheckXColumn(SpinnerColumn):
    """Spinner while running, ✅ on success, ❌ on failure."""
    def render(self, task: Task) -> RenderableType:
        if task.fields.get("error_happened", False):
            return "❌"
        return super().render(task)
