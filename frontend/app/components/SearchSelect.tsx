"use client";

import { ChevronDown, Search } from "lucide-react";
import { KeyboardEvent, useEffect, useId, useMemo, useRef, useState } from "react";

export type SearchSelectOption = {
  value: string;
  label: string;
  detail?: string;
  searchText?: string;
};

function normalizeSearch(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
}

export default function SearchSelect({
  disabled,
  emptyLabel = "Nenhum resultado encontrado",
  name,
  options,
  value,
  onChange
}: {
  disabled?: boolean;
  emptyLabel?: string;
  name?: string;
  options: SearchSelectOption[];
  value: string;
  onChange: (value: string) => void;
}) {
  const listboxId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const selectedOption = options.find((option) => option.value === value) ?? options[0];
  const filteredOptions = useMemo(() => {
    const normalizedQuery = normalizeSearch(query);
    if (!normalizedQuery) return options;

    return options.filter((option) =>
      normalizeSearch(`${option.value} ${option.label} ${option.detail ?? ""} ${option.searchText ?? ""}`).includes(
        normalizedQuery
      )
    );
  }, [options, query]);
  const [activeIndex, setActiveIndex] = useState(0);
  const activeOption = filteredOptions[activeIndex] ?? filteredOptions[0];

  useEffect(() => {
    if (!open) return;

    function closeOnOutsideClick(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    }

    document.addEventListener("mousedown", closeOnOutsideClick);
    return () => document.removeEventListener("mousedown", closeOnOutsideClick);
  }, [open]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  function selectOption(option: SearchSelectOption) {
    onChange(option.value);
    setOpen(false);
    setQuery("");
    inputRef.current?.blur();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (disabled) return;

    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
      if (!filteredOptions.length) return;
      const direction = event.key === "ArrowDown" ? 1 : -1;
      setActiveIndex((index) => (index + direction + filteredOptions.length) % filteredOptions.length);
      return;
    }

    if (event.key === "Enter") {
      event.preventDefault();
      if (activeOption) selectOption(activeOption);
      return;
    }

    if (event.key === "Escape") {
      setOpen(false);
      setQuery("");
      inputRef.current?.blur();
    }
  }

  return (
    <div
      className={`searchSelect${open ? " open" : ""}`}
      ref={rootRef}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) {
          setOpen(false);
          setQuery("");
        }
      }}
    >
      {name ? <input type="hidden" name={name} value={selectedOption.value} /> : null}
      <div className="searchSelectControl">
        <Search size={13} aria-hidden="true" />
        <input
          ref={inputRef}
          disabled={disabled}
          role="combobox"
          aria-expanded={open}
          aria-controls={listboxId}
          aria-autocomplete="list"
          value={open ? query : selectedOption.label}
          onFocus={() => setOpen(true)}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
          }}
          onKeyDown={handleKeyDown}
        />
        <ChevronDown size={14} aria-hidden="true" />
      </div>
      {open ? (
        <div className="searchSelectPopover" id={listboxId} role="listbox">
          {filteredOptions.length ? (
            filteredOptions.map((option, index) => (
              <button
                type="button"
                className={`searchSelectOption${option.detail ? " withDetail" : ""}${
                  option.value === selectedOption.value ? " selected" : ""
                }${index === activeIndex ? " active" : ""}`}
                key={option.value}
                role="option"
                aria-selected={option.value === selectedOption.value}
                onMouseEnter={() => setActiveIndex(index)}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => selectOption(option)}
              >
                {option.detail ? (
                  <>
                    <strong>{option.value}</strong>
                    <span>{option.detail}</span>
                  </>
                ) : (
                  <span>{option.label}</span>
                )}
              </button>
            ))
          ) : (
            <span className="searchSelectEmpty">{emptyLabel}</span>
          )}
        </div>
      ) : null}
    </div>
  );
}
