import {useState} from "react"

import IntegrationDetail from "./components/IntegrationDetail"
import IntegrationGrid from "./components/IntegrationGrid"

export default function Tools() {
    const [selectedIntegration, setSelectedIntegration] = useState<string | null>(null)

    if (selectedIntegration) {
        return (
            <IntegrationDetail
                integrationKey={selectedIntegration}
                onBack={() => setSelectedIntegration(null)}
            />
        )
    }

    return <IntegrationGrid onSelect={setSelectedIntegration} />
}
