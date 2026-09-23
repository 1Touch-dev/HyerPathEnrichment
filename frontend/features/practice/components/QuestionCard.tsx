import { Badge } from "@/components/ui/badge";
import { InterviewQuestion } from "@/src/lib/types";

interface QuestionCardProps {
  question: InterviewQuestion;
}

export function QuestionCard({ question }: QuestionCardProps) {
  return (
    <div className="rounded-[1.25rem] border border-border/70 bg-surface p-5 shadow-panel">
      <p className="text-base font-medium tracking-tight">{question.questionText}</p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Badge variant="outline">{question.category}</Badge>
        <Badge variant="outline">{question.difficulty}</Badge>
        {question.isPersonalized && <Badge variant="success">Personalized</Badge>}
      </div>
    </div>
  );
}
