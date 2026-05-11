import type {FullResult, Reporter, TestCase, TestResult} from "@playwright/test/reporter"

const STATUS_LABEL: Record<string, string> = {
    passed: "PASSED:  ",
    failed: "FAILED:  ",
    timedOut: "TIMEOUT: ",
    skipped: "SKIPPED: ",
    interrupted: "INTERRUPTED: ",
}

const stripAnsi = (str: string) => str.replace(/\x1b\[[0-9;]*m/g, "")

function printError(
    error: {
        message?: string
        stack?: string
        location?: {file: string; line: number; column: number}
    },
    indent = "         ",
) {
    if (error.location) {
        console.log(`${indent}@ ${error.location.file}:${error.location.line}`)
    }
    const message = error.message ? stripAnsi(error.message).trim() : ""
    if (message) {
        for (const line of message.split("\n")) {
            console.log(`${indent}${line}`)
        }
    }
    const stack = error.stack ? stripAnsi(error.stack).trim() : ""
    if (stack) {
        const frames = stack
            .split("\n")
            .filter((l) => l.trim().startsWith("at "))
            .slice(0, 10)
        for (const frame of frames) {
            console.log(`${indent}${frame}`)
        }
    }
}

interface FailureRecord {
    title: string
    errors: TestResult["errors"]
    stdout: string
    stderr: string
}

class LiveReporter implements Reporter {
    private counts = {passed: 0, failed: 0, skipped: 0}
    private failures: FailureRecord[] = []

    onTestBegin(test: TestCase): void {
        console.log(`[test] START:   ${test.titlePath().slice(1).join(" > ")}`)
    }

    onTestEnd(test: TestCase, result: TestResult): void {
        const label = STATUS_LABEL[result.status] ?? "UNKNOWN: "
        const title = test.titlePath().slice(1).join(" > ")
        console.log(`[test] ${label} ${title} (${result.duration}ms)`)

        if (result.status === "passed") {
            this.counts.passed++
        } else if (result.status === "skipped") {
            this.counts.skipped++
        } else {
            this.counts.failed++
            for (const error of result.errors) {
                printError(error)
            }
            const stdout = result.stdout
                .map((c) => (typeof c === "string" ? c : c.toString()))
                .join("")
            const stderr = result.stderr
                .map((c) => (typeof c === "string" ? c : c.toString()))
                .join("")
            this.failures.push({title, errors: result.errors, stdout, stderr})
        }
    }

    onEnd(_result: FullResult): void {
        const {passed, failed, skipped} = this.counts

        if (this.failures.length > 0) {
            console.log(`\n${"─".repeat(60)}`)
            console.log(`[test] FAILURES (${this.failures.length})`)
            console.log("─".repeat(60))
            for (const {title, errors, stdout, stderr} of this.failures) {
                console.log(`\n  ✗ ${title}`)
                for (const error of errors) {
                    printError(error, "    ")
                }
                if (stdout.trim()) {
                    console.log("    --- stdout ---")
                    for (const line of stripAnsi(stdout).trim().split("\n")) {
                        console.log(`    ${line}`)
                    }
                }
                if (stderr.trim()) {
                    console.log("    --- stderr ---")
                    for (const line of stripAnsi(stderr).trim().split("\n")) {
                        console.log(`    ${line}`)
                    }
                }
            }
            console.log("─".repeat(60))
        }

        console.log(`\n[test] ${passed} passed, ${failed} failed, ${skipped} skipped`)
    }
}

export default LiveReporter
