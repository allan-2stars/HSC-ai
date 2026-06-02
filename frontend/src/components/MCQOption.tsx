"use client";

interface Option {
  label: string;
  text: string;
  is_correct?: boolean;
  explanation?: string;
}

export default function MCQOption({
  option,
  selected,
  disabled,
  showResult,
  onSelect,
}: {
  option: Option;
  selected: boolean;
  disabled: boolean;
  showResult: boolean;
  onSelect: () => void;
}) {
  let borderClass = "border-border-subtle";
  if (selected && !showResult) borderClass = "border-cta";
  if (showResult && option.is_correct) borderClass = "border-success";
  if (showResult && selected && !option.is_correct) borderClass = "border-error";

  return (
    <button
      onClick={onSelect}
      disabled={disabled}
      className={`w-full text-left p-4 rounded-lg border-2 ${borderClass} bg-surface hover:bg-opacity-80 transition-colors disabled:opacity-60 disabled:cursor-not-allowed`}
    >
      <span className="font-semibold mr-3 text-cta">{option.label}.</span>
      <span className="text-text-primary">{option.text}</span>
      {showResult && option.is_correct && (
        <span className="ml-2 text-success text-sm">(Correct)</span>
      )}
      {showResult && selected && !option.is_correct && (
        <span className="ml-2 text-error text-sm">(Your answer)</span>
      )}
    </button>
  );
}
